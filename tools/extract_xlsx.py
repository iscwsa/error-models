# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Extract an ISCWSA spreadsheet model sheet into library and model JSON.

Usage: python -m tools.extract_xlsx --workbooks DIR --sheet NAME --library iscwsa:rev5 [--out DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import openpyxl

from tools.formula import canonical
from tools.identity import entry_uuid, library_uuid, model_uuid, stamp
from tools.sheet import WORKBOOKS_FILE, Sheet, SheetTerm, WorkbookError, check_workbook, read_sheet

PROP = {"R": "Random", "S": "Systematic", "W": "Well", "G": "Global"}
_FLAGS = {"R": (0, 0, 0), "S": (1, 0, 0), "W": (1, 1, 0), "G": (1, 1, 1)}
SCHEMA_BASE = "https://raw.githubusercontent.com/iscwsa/error-models/main/schemas/"
ERRATA_FILE = Path(__file__).resolve().parent / "errata.json"
# SheetTerm attribute -> weighting function field
_FORMULA_FIELDS = {
    "depth": "depth",
    "inclination": "inclination",
    "azimuth": "azimuth",
    "sing_north": "singularity_north",
    "sing_east": "singularity_east",
    "sing_vert": "singularity_vertical",
}
_PARAM = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(.*?)\s*$")


class ExtractError(ValueError):
    pass


def _num(text: str):
    value = float(text)
    return int(value) if value.is_integer() and "." not in text else value


def parse_param(value) -> dict:
    """A sheet parameter cell (number or "<number> <unit>") as a parameter_value."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = int(value) if float(value).is_integer() else value
        return {"value": number, "unit": "-", "text": str(number)}
    m = _PARAM.match(str(value))
    if not m:
        raise ExtractError(f"cannot parse parameter {value!r}")
    unit = re.sub(r"\s+", "", m.group(2)) or "-"
    return {"value": _num(m.group(1)), "unit": unit, "text": str(value)}


def _check_flags(term: SheetTerm) -> None:
    expected = _FLAGS.get(term.prop)
    if expected is None:
        raise ExtractError(f"{term.code}: unknown propagation {term.prop!r}")
    if (term.p1, term.p2, term.p3) != expected:
        raise ExtractError(
            f"{term.code}: P1-P3 {(term.p1, term.p2, term.p3)} do not match Prop. {term.prop!r} {expected}"
        )


def _sheet_formulas(term: SheetTerm) -> dict[str, str]:
    return {
        field: getattr(term, attr) for attr, field in _FORMULA_FIELDS.items() if getattr(term, attr) is not None
    }


def _apply_errata(wf_id: str, wf: dict, raw: dict[str, str], errata: list[dict], library_id: str) -> None:
    for e in errata:
        if e["library"] != library_id or e["weighting_function"] != wf_id:
            continue
        field = e["field"]
        if raw.get(field) != e["sheet_text"]:
            raise ExtractError(
                f"stale erratum on {wf_id}/{field}: sheet text is {raw.get(field)!r}, erratum has {e['sheet_text']!r}"
            )
        corrected = canonical(e["corrected"])
        wf[field] = corrected
        wf.setdefault("errata", []).append({
            "field": field,
            "sheet_text": e["sheet_text"],
            "corrected": corrected,
            "source": e["source"],
            "reason": e["reason"],
            "status": e["status"],
        })


def build_library(library_id: str, sheets: list[Sheet], errata: list[dict]) -> dict:
    wfs: dict[str, dict] = {}
    raws: dict[str, dict[str, str]] = {}
    terms: dict[str, dict] = {}
    for sheet in sheets:
        for t in sheet.terms:
            _check_flags(t)
            raw = _sheet_formulas(t)
            for field in ("depth", "inclination", "azimuth"):
                if field not in raw:
                    raise ExtractError(f"{t.code}: weighting function {t.wf_id} has no {field} formula")
            if t.wf_id in raws:
                if {f: canonical(x) for f, x in raw.items()} != {f: canonical(x) for f, x in raws[t.wf_id].items()}:
                    raise ExtractError(f"weighting function {t.wf_id!r} has different formulas in different terms")
            else:
                wf = {f: canonical(x) for f, x in raw.items()}
                if t.wf_comment:
                    wf["comment"] = t.wf_comment
                wf["source"] = t.wf_source or ""
                wf["uuid"] = entry_uuid(library_id, "weighting_function", t.wf_id)
                wfs[t.wf_id] = wf
                raws[t.wf_id] = raw
            term = {
                "description": t.description,
                "type": t.type,
                "units": t.units,
                "propagation": PROP[t.prop],
                "weighting_function": t.wf_id,
                "uuid": entry_uuid(library_id, "term", t.code),
            }
            if t.code in terms and terms[t.code] != term:
                raise ExtractError(f"term {t.code!r} is defined differently on different sheets")
            terms[t.code] = term
    for e in errata:
        if e["library"] == library_id and e["weighting_function"] not in wfs:
            raise ExtractError(f"erratum names weighting function {e['weighting_function']!r} not in {library_id}")
    for wf_id, wf in wfs.items():
        _apply_errata(wf_id, wf, raws[wf_id], errata, library_id)
    doc = {
        "$schema": SCHEMA_BASE + "library.json",
        "library_id": library_id,
        "uuid": library_uuid(library_id),
        "publisher": "ISCWSA",
        "requires": ["xcl_position_direct"],
        "weighting_functions": wfs,
        "terms": terms,
        "hash_function": "SHA256",
        "hash_value": "",
    }
    return stamp(doc)


def _iso_date(value) -> str:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def _revision(value) -> str:
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def build_model(sheet: Sheet, namespace: str, library: dict) -> dict:
    m = sheet.meta
    prefix = m["OWSG Prefix"]
    meta = {
        "model_uuid": model_uuid(namespace, prefix),
        "model_id": f"{namespace}:{prefix}",
        "short_name": m["Short Name"],
        "long_name": m["Long Name"],
        "revision": _revision(m["Revision No"]),
        "revision_date": _iso_date(m["Revision Date"]),
        "revision_comment": m.get("Revision Comment", ""),
        "source": m["Source"],
        "tool_type": m["Tool Type"],
        "status": "current",
        "framework": "ISCWSA Rev5",
        "author": "ISCWSA",
        "tags": [],
    }
    optional = (
        ("application", "Application"), ("sheet_status", "Status"), ("checked", "Checked"),
        ("approved", "Approved"), ("notes", "Notes"), ("revision_history", "Revision History"),
        ("replaces_text", "Replaces / Replaced By"), ("range_comment", "Range Comment"),
    )
    for key, label in optional:
        value = m.get(label)
        if value not in (None, "", []):
            meta[key] = value
    doc = {
        "$schema": SCHEMA_BASE + "model.json",
        "metadata": meta,
        "origin": {"workbook": sheet.workbook, "sha256": sheet.sha256, "sheet": sheet.name},
        "libraries": [{
            "id": library["library_id"], "uuid": library["uuid"], "hash_value": library["hash_value"],
        }],
        "applicability": {
            "inc_min": parse_param(m["Inclination Range Min"]),
            "inc_max": parse_param(m["Inclination Range Max"]),
            "hor_ew_exclusion": parse_param(m["Hor East/West Exclusion"]),
        },
        "parameters": {re.sub(r"\s+", "", k): parse_param(v) for k, v in sheet.tool_params.items()},
        "terms": [{"term": t.code, "magnitude": t.magnitude} for t in sorted(sheet.terms, key=lambda t: t.no)],
        "hash_function": "SHA256",
        "hash_value": "",
    }
    return stamp(doc)


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent="\t", ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8"))


def _find_workbook(directory: Path, sheet: str) -> tuple[Path, dict]:
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    hits = []
    for name in known:
        path = directory / name
        if not path.is_file():
            continue
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            if sheet in wb.sheetnames:
                hits.append(path)
        finally:
            wb.close()
    if len(hits) != 1:
        raise ExtractError(f"sheet {sheet!r} found in {len(hits)} known workbooks under {directory}; expected exactly 1")
    return hits[0], check_workbook(hits[0])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.extract_xlsx")
    parser.add_argument("--workbooks", required=True, type=Path)
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        path, entry = _find_workbook(args.workbooks.expanduser(), args.sheet)
        sheet = read_sheet(path, args.sheet)
        errata = json.loads(ERRATA_FILE.read_text(encoding="utf-8"))
        library = build_library(args.library, [sheet], errata)
        model = build_model(sheet, entry["namespace"], library)
    except (ExtractError, WorkbookError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    lib_ns, _, lib_name = args.library.partition(":")
    write_json(args.out / "library" / lib_ns / f"{lib_name}.json", library)
    mns, _, mname = model["metadata"]["model_id"].partition(":")
    write_json(args.out / "models" / mns / f"{mname}.json", model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
