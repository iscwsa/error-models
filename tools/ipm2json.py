# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""IPM file -> one model and one vendor library (docs/ipm.md).

A source (the rows of one name) becomes a reference to the ISCWSA library term of the same name when its propagation,
formulas and weights match it (docs/ipm.md, "Matching ISCWSA terms"); otherwise it becomes `<ns>:<NAME>` in the vendor
library `<ns>:<model>_terms`. Nothing is written unless every source converts and the output validates.

Usage: python -m tools.ipm2json --namespace NS --model-id ID --tool-type T --revision-date YYYY-MM-DD --author A
           [--inc-min X --inc-max Y --source S --status S --subsea ...] FILE.ipm --out DIR
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
import tempfile
from pathlib import Path

from tools.diagnostics import read_hpt
from tools.formula import Bin, Call, Node, Num, Var, canonical, parse
from tools.identity import entry_uuid, library_uuid, model_uuid, stamp
from tools.ipm import (FT, JSON_UNITS, SI, TIE_ONS, UNIT_FACTORS, VECTORS, IpmError, IpmFile, IpmRow, is_variable,
                       read_ipm, translate_node)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = "https://raw.githubusercontent.com/iscwsa/error-models/main/schemas/{}.json"
ISCWSA_LIBRARY = ROOT / "library" / "iscwsa" / "rev5.json"
DIAGNOSTICS = ROOT / "conformance" / "vectors" / "iscwsa_rev5-1"
EARTH_RATE = 7.2921159e-5  # rad/s (SPE 90408); the guide's `erot` uses 15.041 deg/hr (docs/ipm.md, "Constants")
TOL = 1e-12                # relative to the largest weight of the source over the stations
TOL_VERTICAL = 1e-6        # at a vertical station, where a 1/Sin(Inc) weight is taken as its limit
VERTICAL_EPS = 1e-9        # rad
FIELD = {"e": "depth", "s": "depth", "i": "inclination", "y": "inclination", "a": "azimuth", "l": "azimuth",
         "x": "azimuth"}
HEADER = {"ShortName": "short_name", "Description": "long_name", "RevisionNumber": "revision",
          "RevisionComment": "revision_comment", "SourceReference": "source", "ToolApplication": "application",
          "CurrentStatus": "sheet_status", "ReplacesTool": "replaces_text", "RangeComment": "range_comment",
          "Remarks": "notes"}
APPLICABILITY = {"InclinationRangeMin": "inc_min", "InclinationRangeMax": "inc_max",
                 "AzimuthEWRestriction": "hor_ew_exclusion"}
REQUIRED = ("short_name", "long_name", "revision", "revision_date", "revision_comment", "source", "tool_type",
            "author", "inc_min", "inc_max", "hor_ew_exclusion")
_SIN_INC = Call("Sin", (Var("Inc"),))


# ---------------------------------------------------------------- stations
@functools.lru_cache(maxsize=None)
def station_envs(diagnostics: Path = DIAGNOSTICS) -> tuple:
    """One formula environment per station of the ISCWSA Rev 5.1 diagnostic wells (radians, metres)."""
    envs = []
    for path in sorted(Path(diagnostics).glob("*.dat")):
        d = read_hpt(path)
        w, prev = d.well, None
        for s in d.stations:
            env = {"MD": s.md, "TVD": s.tvd, "Inc": math.radians(s.inc), "AzT": math.radians(s.azt),
                   "AzM": math.radians(s.azt - w["Declination"]), "TF": math.radians(s.tf),
                   "Dip": math.radians(w["Dip"]), "Lat": math.radians(w["Latitude"]), "BField": w["BTotal"],
                   "GField": w["GTotal"], "EarthRate": EARTH_RATE}
            env["Az"] = env["AzT"]
            p = prev or env
            env.update(MDPrev=p["MD"], IncPrev=p["Inc"], AzPrev=p["AzT"])
            envs.append(env)
            prev = env
    return tuple(envs)


def _values(node: Node, envs) -> list[float]:
    return [node.evaluate(e) for e in envs]


def _lateral(node: Node, env) -> float:
    """An azimuth weight times Sin(Inc); at a vertical station its limit (Inc -> VERTICAL_EPS)."""
    v = node.evaluate(env) * math.sin(env["Inc"])
    if not math.isfinite(v) and env["Inc"] == 0.0:
        e = dict(env, Inc=VERTICAL_EPS)
        v = node.evaluate(e) * math.sin(VERTICAL_EPS)
    return v


def _close(a, b, envs=None) -> bool:
    scale = max((abs(y) for y in b if math.isfinite(y)), default=0.0)
    for k, (x, y) in enumerate(zip(a, b)):
        if math.isfinite(x) != math.isfinite(y):
            return False
        tol = TOL_VERTICAL if envs is not None and envs[k]["Inc"] == 0.0 else TOL
        if math.isfinite(x) and abs(x - y) > tol * scale:
            return False
    return True


# ---------------------------------------------------------------- sources
def _check_row(r: IpmRow):
    if r.start_inc is not None or r.end_inc is not None:
        raise IpmError("range", r)
    if r.vector not in VECTORS:
        raise IpmError(f"vector:{r.vector}", r)
    if r.tie_on not in TIE_ONS:
        raise IpmError(f"tie_on:{r.tie_on}", r)
    if r.unit not in JSON_UNITS:
        raise IpmError(f"unit:{r.unit}", r)


def sources(ipm: IpmFile, subsea: bool = False) -> list[tuple[str, list[IpmRow]]]:
    """The file's error sources in file order: (name, rows), after the subset checks of docs/ipm.md."""
    if not ipm.rows and not ipm.layout:     # a file of the layout with no rows is a zero-error tool (no sources)
        raise IpmError("no_rows", None, "not the guide's layout (no Name / Vector / Tie-On / Unit column titles)")
    for r in ipm.rows:
        if is_variable(r):
            raise IpmError("variable", r)
        _check_row(r)
    subsea_names = {r.name.lower() for r in ipm.rows if r.vector == "s"}
    groups: dict[str, list[IpmRow]] = {}
    for r in ipm.rows:
        if r.vector == "s" and not subsea or r.vector == "e" and subsea and r.name.lower() in subsea_names:
            continue
        groups.setdefault(r.name.lower(), []).append(r)
    out = []
    for rows in groups.values():
        if len({r.tie_on for r in rows}) > 1:
            raise IpmError("mixed_tie_on", rows[1])
        seen = set()
        for r in rows:
            if FIELD[r.vector] in seen:
                raise IpmError("repeated_vector", r)
            seen.add(FIELD[r.vector])
        kinds = {"depth" if r.vector in "es" else "xcl" if r.vector in "xy" else "angle" for r in rows}
        if len(kinds) > 1:
            raise IpmError("mixed_vectors", rows[-1])
        out.append((rows[0].name, rows))
    return out


def _unit(rows) -> str:
    first = rows[0]
    if first.unit == "d" and any("erot" in r.formula.lower() for r in rows):
        return "deg/hr"
    return JSON_UNITS[first.unit]


def source_term(rows: list[IpmRow], envs=None) -> tuple[float, str, dict[str, str], dict[str, str]]:
    """(magnitude, units, {depth, inclination, azimuth}, singularity formulas) of one source. Each row takes the natural
    reading when it equals the literal one at every station, and otherwise the literal one times its exact factor.
    An `l` or `x` row is a lateral weight F: its azimuth formula is F / Sin(Inc), and its singularity formulas are F
    along the lateral direction at a vertical station (north -F Sin(AzT), east F Cos(AzT), vertical 0)."""
    envs = station_envs() if envs is None else envs
    unit = _unit(rows)
    first = rows[0]
    magnitude = abs(first.value * (0.001 if first.unit == "t" else 1.0))
    denom = (magnitude or 1.0) * SI[unit]
    fields = {"depth": "0", "inclination": "0", "azimuth": "0"}
    singular = {}
    for r in rows:
        depth = r.vector in "es"
        s = r.value * UNIT_FACTORS.get(r.unit, 1.0) * (FT if depth else 1.0) / denom
        lit = translate_node(r.formula, "literal", row=r)
        nat = translate_node(r.formula, "natural", row=r)
        want = [s * v for v in _values(lit, envs)]
        if _close(_values(nat, envs), want):
            node = nat
        else:
            node = lit if s == 1.0 else Bin("*", Num(s), lit)
        if r.vector in "lx":
            lateral = node.render()
            singular = {"singularity_north": canonical(f"-({lateral}) * Sin(AzT)"),
                        "singularity_east": canonical(f"({lateral}) * Cos(AzT)"), "singularity_vertical": "0"}
            node = Bin("/", node, _SIN_INC)
        fields[FIELD[r.vector]] = canonical(node.render())
    return magnitude, unit, fields, singular


def _ipm_weights(rows, envs):
    """Per-station (depth m, inclination rad, lateral rad) weights of one source, read literally (the IPM meaning)."""
    d, i, lat = ([0.0] * len(envs) for _ in range(3))
    for r in rows:
        node = translate_node(r.formula, "literal", row=r)
        f = r.value * UNIT_FACTORS.get(r.unit, 1.0)
        for k, env in enumerate(envs):
            if r.vector in "es":
                d[k] += f * node.evaluate(env) * FT
            elif r.vector in "iy":
                i[k] += f * node.evaluate(env)
            elif r.vector in "lx":
                lat[k] += f * node.evaluate(env)
            else:
                lat[k] += f * _lateral(node, env)
    return d, i, lat


def _json_weights(magnitude, unit, wf, envs):
    m = magnitude * SI[unit]
    d = [m * v for v in _values(parse(wf["depth"]), envs)]
    i = [m * v for v in _values(parse(wf["inclination"]), envs)]
    az = parse(wf["azimuth"])
    lat = [m * _lateral(az, e) for e in envs]
    return d, i, lat


def _same_weights(a, b, envs) -> bool:
    return all(_close(x, y, envs) for x, y in zip(a, b))


def _match(name, tie, magnitude, unit, fields, library, envs):
    """(iscwsa code, magnitude in its units) when the source is that library term, else (None, reason)."""
    by_upper = {k.upper(): k for k in library["terms"]}
    code = by_upper.get(name.upper())
    if code is None:
        return None, None
    term = library["terms"][code]
    wf = library["weighting_functions"][term["weighting_function"]]
    if "mode" in term:
        return None, f"not iscwsa:{code}: a gyro survey-mode term"
    if term["propagation"] != TIE_ONS[tie]:
        return None, f"not iscwsa:{code}: propagation {TIE_ONS[tie]} is not {term['propagation']}"
    if SI[term["units"]] != SI[unit]:
        return None, f"not iscwsa:{code}: units {unit} are not {term['units']}"
    for f in ("depth", "inclination", "azimuth"):
        if canonical(wf[f]) != fields[f]:
            return None, f"not iscwsa:{code}: {f} formula {fields[f]!r} is not {canonical(wf[f])!r}"
    lib_w = _json_weights(1.0, term["units"], wf, envs)
    own_w = _json_weights(1.0, unit, fields, envs)
    if not _same_weights(own_w, lib_w, envs):
        return None, f"not iscwsa:{code}: weights differ"
    return code, magnitude if unit == term["units"] else magnitude * SI[unit] / SI[term["units"]]


def _same_as(tie, fields, library) -> list[str]:
    out = []
    for code, term in library["terms"].items():
        wf = library["weighting_functions"][term["weighting_function"]]
        if term["propagation"] == TIE_ONS[tie] and all(canonical(wf[f]) == fields[f] for f in fields):
            out.append(code)
    return out


def _ref(lib: dict) -> dict:
    return {"id": lib["library_id"], "uuid": lib["uuid"], "hash_value": lib["hash_value"]}


def _param(value: float, unit: str = "deg") -> dict:
    return {"value": value, "unit": unit, "text": f"{value:g} {unit}"}


def metadata(header: dict, flags: dict) -> dict:
    """Model metadata from the IPM header (docs/ipm.md, "Metadata") and the command-line flags, which win. A required
    field with neither source raises IpmError("missing:<field>")."""
    out = {v: header[k] for k, v in HEADER.items() if header.get(k, "").strip()}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", header.get("RevisionDate", "").strip()):
        out["revision_date"] = header["RevisionDate"].strip()   # only an ISO date: '01/11/2013' could be either order
    for k, v in APPLICABILITY.items():
        if header.get(k, "").strip():
            try:
                out[v] = float(header[k])
            except ValueError:
                raise IpmError("syntax", None, f"header {k} {header[k]!r} is not a number") from None
    out.update({k: v for k, v in flags.items() if v is not None})
    for f in REQUIRED:
        if f not in out:
            raise IpmError(f"missing:{f}", None, f"give --{f.replace('_', '-')}")
    return out


def convert(ipm: IpmFile, namespace: str, meta: dict, iscwsa_library: dict, subsea: bool = False,
            envs=None) -> tuple[dict, dict | None, list[str]]:
    """(model, vendor library or None when every source is an ISCWSA term, log lines). `meta` is `metadata()`'s
    output plus `model_id` (the name part)."""
    envs = station_envs() if envs is None else envs
    name = meta["model_id"]
    lib_id = f"{namespace}:{name}_terms"
    log, terms, wfs, lib_terms = [], [], {}, {}
    for src, rows in sources(ipm, subsea):
        tie = rows[0].tie_on
        magnitude, unit, fields, singular = source_term(rows, envs)
        code, info = _match(src, tie, magnitude, unit, fields, iscwsa_library, envs)
        if code is not None:
            terms.append({"term": code, "magnitude": info})
            log.append(f"{src}: iscwsa:{code}")
            continue
        if info:
            log.append(f"{src}: {info}")
        key = src.upper()
        same = _same_as(tie, fields, iscwsa_library)
        if same:
            log.append(f"{src}: same_as {', '.join('iscwsa:' + c for c in same)}")
        wfs[key] = dict(fields, **singular, source=meta["source"], uuid=entry_uuid(lib_id, "weighting_function", key))
        term = {"description": src, "type": "IPM", "units": unit, "propagation": TIE_ONS[tie],
                "weighting_function": key, "uuid": entry_uuid(lib_id, "term", key)}
        if any(r.vector in "xy" for r in rows):
            term["requires"] = ["xcl_position_direct"]
        lib_terms[key] = term
        terms.append({"term": f"{namespace}:{key}", "magnitude": magnitude})
        log.append(f"{src}: {namespace}:{key}")
    vendor = None
    if lib_terms:
        vendor = stamp({
            "$schema": SCHEMA_URL.format("library"), "library_id": lib_id, "uuid": library_uuid(lib_id),
            "publisher": meta["author"], "extends": [_ref(iscwsa_library)],
            "requires": sorted({c for t in lib_terms.values() for c in t.get("requires", [])}),
            "weighting_functions": wfs, "terms": lib_terms, "hash_function": "SHA256"})
    md = {"model_uuid": model_uuid(namespace, name), "model_id": f"{namespace}:{name}"}
    for f in ("short_name", "long_name", "revision", "revision_date", "revision_comment", "source", "tool_type"):
        md[f] = meta[f]
    md.update(status=meta.get("status") or "current", framework="Other", author=meta["author"], tags=[])
    for f in ("application", "sheet_status", "notes", "replaces_text", "range_comment"):
        if meta.get(f):
            md[f] = meta[f]
    model = stamp({
        "$schema": SCHEMA_URL.format("model"), "metadata": md,
        "origin": {"file": ipm.file, "sha256": ipm.sha256},
        "libraries": [_ref(iscwsa_library)] + ([_ref(vendor)] if vendor else []),
        "applicability": {"inc_min": _param(meta["inc_min"]), "inc_max": _param(meta["inc_max"]),
                          "hor_ew_exclusion": _param(meta["hor_ew_exclusion"])},
        "parameters": {}, "terms": terms, "hash_function": "SHA256"})
    return model, vendor, log


def weights_equal(model: dict, libraries: list[dict], ipm: IpmFile, subsea: bool = False, envs=None) -> bool:
    """The model's per-term weights equal the IPM's (read literally) at every station (docs/ipm.md, condition 4)."""
    envs = station_envs() if envs is None else envs
    libs = {lib["library_id"].split(":", 1)[0]: lib for lib in libraries}
    ipm_w = {name.upper(): _ipm_weights(rows, envs) for name, rows in sources(ipm, subsea)}
    if len(ipm_w) != len(model["terms"]):
        return False
    for t in model["terms"]:
        ns, _, key = t["term"].rpartition(":")
        lib = libs.get(ns or "iscwsa")
        if lib is None or key.upper() not in ipm_w:
            return False
        term = lib["terms"][key]
        own = _json_weights(t["magnitude"], term["units"], lib["weighting_functions"][term["weighting_function"]], envs)
        if not _same_weights(own, ipm_w[key.upper()], envs):
            return False
    return True


def dump(doc: dict) -> str:
    return json.dumps(doc, indent="\t", ensure_ascii=False) + "\n"


def write(model: dict, vendor: dict | None, out: Path, iscwsa_library_path: Path = ISCWSA_LIBRARY) -> list[Path]:
    """Validate the new files next to the ISCWSA library in a temporary tree, then write them under `out`."""
    from tools.validate import validate_repo

    ns, _, name = model["metadata"]["model_id"].partition(":")
    files = {Path("models") / ns / f"{name}.json": model}
    if vendor is not None:
        files[Path("library") / ns / f"{vendor['library_id'].partition(':')[2]}.json"] = vendor
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        lib_rel = Path("library") / "iscwsa" / iscwsa_library_path.name
        (t / lib_rel).parent.mkdir(parents=True)
        (t / lib_rel).write_bytes(iscwsa_library_path.read_bytes())
        for rel, doc in files.items():
            (t / rel).parent.mkdir(parents=True, exist_ok=True)
            (t / rel).write_text(dump(doc), encoding="utf-8", newline="\n")
        rels = {rel.as_posix() for rel in files}
        problems = [p for p in validate_repo(t) if p.file in rels]
        if problems:
            raise IpmError("invalid", None, "; ".join(f"{p.file}: {p.code}: {p.detail}" for p in problems))
    written = []
    for rel, doc in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(dump(doc), encoding="utf-8", newline="\n")
        written.append(out / rel)
    return written


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.ipm2json")
    p.add_argument("file", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--model-id", required=True)
    for f in ("tool-type", "revision-date", "author", "source", "status", "short-name", "long-name", "revision",
              "revision-comment"):
        p.add_argument(f"--{f}")
    for f in ("inc-min", "inc-max", "hor-ew-exclusion"):
        p.add_argument(f"--{f}", type=float)
    p.add_argument("--subsea", action="store_true")
    a = p.parse_args(argv)
    try:
        ipm = read_ipm(a.file)
        flags = {k: getattr(a, k) for k in ("tool_type", "revision_date", "author", "source", "short_name",
                                             "long_name", "revision", "revision_comment", "inc_min", "inc_max",
                                             "hor_ew_exclusion")}
        meta = dict(metadata(ipm.header, flags), model_id=a.model_id, status=a.status)
        library = json.loads(ISCWSA_LIBRARY.read_text(encoding="utf-8"))
        model, vendor, log = convert(ipm, a.namespace, meta, library, a.subsea)
        for path in write(model, vendor, a.out):
            print(f"wrote {path}")
    except IpmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for line in log:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
