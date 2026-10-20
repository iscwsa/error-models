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
from tools.inventory import ModelId, load_model_ids
from tools.identity import entry_uuid, library_uuid, model_uuid, stamp
from tools.sheet import WORKBOOKS_FILE, Sheet, SheetTerm, WorkbookError, check_workbook, read_sheet, read_workbook

PROP = {"R": "Random", "S": "Systematic", "W": "Well", "G": "Global", "B": "Bias"}
# "B" (SPE 67616 bias terms, ISCWSA MWD bias Rev0-2 sheets) carries P flags 0,0,0 like "R"
_FLAGS = {"R": (0, 0, 0), "S": (1, 0, 0), "W": (1, 1, 0), "G": (1, 1, 1), "B": (0, 0, 0)}
SCHEMA_BASE = "https://raw.githubusercontent.com/iscwsa/error-models/main/schemas/"
ERRATA_FILE = Path(__file__).resolve().parent / "errata.json"
TERM_REQUIRES_FILE = Path(__file__).resolve().parent / "term_requires.json"
TERM_GROUPS_FILE = Path(__file__).resolve().parent / "term_groups.json"
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
_NOTE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*\[[^\]]*\]\s*$")
# sheet tool-parameter label -> JSON key; an unlisted label is an error, never guessed
PARAM_NAMES = {
    "Misalignment Alt": "MisalignmentAlt",
    "Misalignment Min Course Length": "MisalignmentMinCourseLength",
    "Misalignment Minimum Course Length": "MisalignmentMinCourseLength",
    "XCL Tortuosity": "XCLTortuosity",
    "Start Inc": "StartInc",
    "End Inc": "EndInc",
    "Initialisation Inc": "InitialisationInc",
    "Running Speed": "RunningSpeed",
    "Min Dist Between Inits": "MinDistBetweenInits",
    "Noise Reduction Factor": "NoiseReductionFactor",
    "XYZ Accelerometer": "XYZAccelerometer",
    "XY Static Gyro": "XYStaticGyro",
    "XY Continuous Gyro": "XYContinuousGyro",
    "Z Continuous Gyro": "ZContinuousGyro",
    "External Ref": "ExternalRef",
}
_FRAMEWORKS = {"iscwsa:rot6axis": "ISCWSA RCS", **{f"iscwsa:rev{n}": f"ISCWSA Rev{n}" for n in range(6)}}
_QUALIFIED = re.compile(r"[A-Za-z0-9_]+:[A-Za-z0-9_]+")


class ExtractError(ValueError):
    pass


def _num(text: str):
    value = float(text)
    return int(value) if value.is_integer() and "." not in text else value


def parse_param(value) -> dict:
    """A sheet parameter cell (number or "<number> <unit>") as a parameter_value."""
    if isinstance(value, bool) or str(value).strip() in ("True", "False"):
        flag = value if isinstance(value, bool) else str(value).strip() == "True"
        return {"value": flag, "unit": "-", "text": str(value).strip()}
    if isinstance(value, (int, float)):
        number = int(value) if float(value).is_integer() else value
        return {"value": number, "unit": "-", "text": str(number)}
    n = _NOTE.match(str(value))
    if n:   # a bracketed note is text, never a unit
        return {"value": _num(n.group(1)), "unit": "-", "text": str(value)}
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


def build_library(library_id: str, sheets: list[Sheet], errata: list[dict], groups: list[dict] | None = None,
                  log: list[str] | None = None, term_requires: dict[str, list[str]] | None = None) -> dict:
    """One library from its sheets. `log` receives a line for each wf_comment/wf_source conflict (first one kept)."""
    if term_requires is None:
        term_requires = json.loads(TERM_REQUIRES_FILE.read_text(encoding="utf-8"))
    logged: set[tuple[str, str, str]] = set()
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
                kept = {"wf_comment": wfs[t.wf_id].get("comment", ""), "wf_source": wfs[t.wf_id]["source"]}
                seen = {"wf_comment": t.wf_comment or "", "wf_source": t.wf_source or ""}
                for field in ("wf_comment", "wf_source"):
                    key = (t.wf_id, field, seen[field])
                    if seen[field] != kept[field] and key not in logged and log is not None:
                        logged.add(key)
                        log.append(f"{library_id}: weighting function {t.wf_id}: {field} {seen[field]!r} "
                                   f"(term {t.code}, sheet {sheet.name!r}) differs from the kept {kept[field]!r}")
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
            if t.code in term_requires:
                term["requires"] = list(term_requires[t.code])
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
        "requires": sorted({cap for term in terms.values() for cap in term.get("requires", [])}),
        "weighting_functions": wfs,
        "terms": terms,
        "hash_function": "SHA256",
        "hash_value": "",
    }
    if groups:
        doc["term_groups"] = groups
    return stamp(doc)


def build_libraries(sheets_by_library: dict[str, list[Sheet]], errata: list[dict], groups: dict,
                    log: list[str] | None = None) -> dict[str, dict]:
    """Every library from the sheets that tools/model_ids.csv assigns to it, with its term_groups."""
    term_requires = json.loads(TERM_REQUIRES_FILE.read_text(encoding="utf-8"))
    out = {lib_id: build_library(lib_id, sheets, errata, groups.get(lib_id), log, term_requires)
           for lib_id, sheets in sheets_by_library.items()}
    defined = {code for lib in out.values() for code in lib["terms"]}
    if len(out) > 1 and set(term_requires) - defined:
        raise ExtractError(f"tools/term_requires.json names unknown terms {sorted(set(term_requires) - defined)}")
    return out


def _iso_date(value) -> str:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def _revision(value) -> str:
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _status(sheet: Sheet, model_id: ModelId) -> str:
    if model_id.library == "iscwsa:rot6axis":
        return "candidate"
    text = sheet.meta.get("Status")
    if text == "Agreed":
        return "current"
    if text == "Obsolete":
        return "superseded"
    raise ExtractError(f"sheet {sheet.name!r}: unknown Status {text!r}")


def _param_key(label: str, sheet: Sheet) -> str:
    try:
        return PARAM_NAMES[label]
    except KeyError:
        raise ExtractError(f"sheet {sheet.name!r}: unknown tool parameter label {label!r}") from None


def _related(text, all_ids: set[str]) -> tuple[list[str], list[str]]:
    """Qualified repo IDs named before / after the "/" of `Replaces / Replaced By`; nothing else resolves."""
    before, _, after = str(text or "").partition("/")
    pick = lambda part: sorted({t for t in _QUALIFIED.findall(part) if t in all_ids})
    return pick(before), pick(after)


def build_model(sheet: Sheet, model_id: ModelId, library: dict, all_ids: set[str]) -> dict:
    m = sheet.meta
    qualified = f"{model_id.namespace}:{model_id.model_id}"
    if library["library_id"] != model_id.library:
        raise ExtractError(f"{qualified}: library {library['library_id']!r} is not the model's library {model_id.library!r}")
    framework = _FRAMEWORKS.get(model_id.library)
    if framework is None:
        raise ExtractError(f"{qualified}: no framework for library {model_id.library!r}")
    supersedes, superseded_by = _related(m.get("Replaces / Replaced By"), all_ids)
    meta = {
        "model_uuid": model_uuid(model_id.namespace, model_id.model_id),
        "model_id": qualified,
        "short_name": m["Short Name"],
        "long_name": m["Long Name"],
        "revision": _revision(m["Revision No"]),
        "revision_date": _iso_date(m["Revision Date"]),
        "revision_comment": m.get("Revision Comment", ""),
        "source": m["Source"],
        "tool_type": m["Tool Type"],
        "status": _status(sheet, model_id),
        "framework": framework,
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
    if supersedes:
        meta["supersedes"] = supersedes
    if superseded_by:
        meta["superseded_by"] = superseded_by
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
        "parameters": {_param_key(k, sheet): parse_param(v) for k, v in sheet.tool_params.items()},
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


def _read_all(workbooks: Path) -> list[tuple[ModelId, Sheet]]:
    """Every model sheet of every workbook in tools/workbooks.json, with its ID, in workbook then sheet order."""
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    ids = load_model_ids()
    out: list[tuple[ModelId, Sheet]] = []
    for name, entry in known.items():
        path = workbooks / name
        check_workbook(path)
        sheets, _ = read_workbook(path)
        for sheet in sheets:
            model_id = ids.get((entry["iscwsa_file"], sheet.name))
            if model_id is None:
                raise ExtractError(f"sheet {sheet.name!r} (file {entry['iscwsa_file']}) is not in tools/model_ids.csv")
            out.append((model_id, sheet))
    return out


def _build_libraries_from(pairs: list[tuple[ModelId, Sheet]], log: list[str]) -> dict[str, dict]:
    by_library: dict[str, list[Sheet]] = {}
    for model_id, sheet in pairs:
        by_library.setdefault(model_id.library, []).append(sheet)
    errata = json.loads(ERRATA_FILE.read_text(encoding="utf-8"))
    groups = json.loads(TERM_GROUPS_FILE.read_text(encoding="utf-8"))
    return build_libraries(by_library, errata, groups, log)


def build_all_libraries(workbooks: Path, log: list[str]) -> dict[str, dict]:
    """Read every workbook in tools/workbooks.json and build the libraries tools/model_ids.csv names."""
    return _build_libraries_from(_read_all(workbooks), log)


def _fmt_mag(value) -> str:
    return repr(value)


def log_magnitude_differences(pairs: list[tuple[ModelId, Sheet]], log: list[str]) -> None:
    """Log every term whose magnitude differs between Generic sheets of one family.

    A family is the set of Generic (generic_iscwsa) sheets with the same `Tool Type` (Magnetic, Gyro, ...). Within a
    family, a term code that has more than one magnitude is logged once, as
    `magnitude_diff: family=<Tool Type> term=<code> <mag> in [<sheets>]; <mag> in <n> sheets`; groups of up to four
    sheets name them, larger groups give the count. Nothing is changed: this is for the user to review.
    """
    families: dict[str, list[Sheet]] = {}
    for model_id, sheet in pairs:
        if model_id.namespace == "generic_iscwsa":
            families.setdefault(str(sheet.meta["Tool Type"]), []).append(sheet)
    for family in sorted(families):
        by_term: dict[str, dict[float, list[str]]] = {}
        for sheet in families[family]:
            for t in sheet.terms:
                by_term.setdefault(t.code, {}).setdefault(t.magnitude, []).append(sheet.name)
        for code in sorted(by_term):
            groups = by_term[code]
            if len(groups) < 2:
                continue
            parts = [f"{_fmt_mag(mag)} in [{', '.join(names)}]" if len(names) <= 4 else f"{_fmt_mag(mag)} in {len(names)} sheets"
                     for mag, names in sorted(groups.items(), key=lambda kv: (len(kv[1]), kv[0]))]
            log.append(f"magnitude_diff: family={family} term={code} " + "; ".join(parts))


def build_all(workbooks: Path, log: list[str]) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    """(libraries by ID, models by (namespace, model_id)) for every sheet; the log lists conflicts and differences."""
    pairs = _read_all(workbooks)
    libraries = _build_libraries_from(pairs, log)
    all_ids = {f"{m.namespace}:{m.model_id}" for m, _ in pairs}
    models = {(m.namespace, m.model_id): build_model(sheet, m, libraries[m.library], all_ids) for m, sheet in pairs}
    log_magnitude_differences(pairs, log)
    return libraries, models


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.extract_xlsx")
    parser.add_argument("--workbooks", required=True, type=Path)
    parser.add_argument("--all-libraries", action="store_true", help="build the seven libraries from every sheet")
    parser.add_argument("--all", action="store_true", help="build the seven libraries and every model")
    parser.add_argument("--sheet")
    parser.add_argument("--library")
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    if args.all:
        log: list[str] = []
        try:
            libraries, models = build_all(args.workbooks.expanduser(), log)
        except (ExtractError, WorkbookError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        for lib_id, library in libraries.items():
            ns, _, name = lib_id.partition(":")
            write_json(args.out / "library" / ns / f"{name}.json", library)
        for (ns, name), model in models.items():
            write_json(args.out / "models" / ns / f"{name}.json", model)
        for line in log:
            print(f"log: {line}", file=sys.stderr)
        return 0
    if args.all_libraries:
        log: list[str] = []
        try:
            libraries = build_all_libraries(args.workbooks.expanduser(), log)
        except (ExtractError, WorkbookError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        for lib_id, library in libraries.items():
            ns, _, name = lib_id.partition(":")
            write_json(args.out / "library" / ns / f"{name}.json", library)
        for line in log:
            print(f"log: {line}", file=sys.stderr)
        return 0
    if not (args.sheet and args.library):
        parser.error("--sheet and --library are required unless --all or --all-libraries is given")
    try:
        path, entry = _find_workbook(args.workbooks.expanduser(), args.sheet)
        sheet = read_sheet(path, args.sheet)
        errata = json.loads(ERRATA_FILE.read_text(encoding="utf-8"))
        library = build_library(args.library, [sheet], errata)
        ids = load_model_ids()
        model_id = ids.get((entry["iscwsa_file"], args.sheet))
        if model_id is None:
            raise ExtractError(f"sheet {args.sheet!r} (file {entry['iscwsa_file']}) is not in tools/model_ids.csv")
        all_ids = {f"{i.namespace}:{i.model_id}" for i in ids.values()}
        model = build_model(sheet, model_id, library, all_ids)
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
