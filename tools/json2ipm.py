# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""A model -> Compass IPM text (docs/ipm.md, "JSON to IPM").

One row per term per non-zero depth / inclination / azimuth formula, in model term order. Singularity formulas are not
written (IPM has no field for them); a matched ISCWSA term gets them back from the library on the way in.
Refused: gyro models and survey-mode terms, Bias terms, units with no IPM unit, and any formula variable with no IPM
equivalent (IpmError naming it).

Usage: python -m tools.json2ipm MODEL.json [--root DIR] > FILE.ipm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.formula import Bin, Call, Var, canonical, parse
from tools.ipm import FT, SI, TIE_ONS, UNIT_FACTORS, IpmError, to_ipm, translate_node
from tools.ipm2json import HEADER, _close, _values, station_envs

ROOT = Path(__file__).resolve().parent.parent
IPM_UNITS = {"-": "-", "m": "m", "1/m": "im", "deg": "d", "deg.nT": "dnt", "nT": "nt", "m/s2": "-", "deg/hr": "d"}
TIE = {v: k for k, v in TIE_ONS.items()}
COLUMNS = "Name\tVector\tTie-On\tUnit\tValue\tFormula"


def _formula(text: str, unit: str, depth: bool, envs) -> str:
    """IPM text whose literal reading, times the row's unit factor, is the JSON formula times the unit's SI factor."""
    iu = IPM_UNITS[unit]
    c = SI[unit] / (UNIT_FACTORS.get(iu, 1.0) * (FT if depth else 1.0))
    nat = to_ipm(text, "natural")                       # refuses a variable with no IPM equivalent first
    want = [c * v for v in _values(parse(text), envs)]
    if _close(_values(translate_node(nat, "literal"), envs), want):
        return nat
    lit = to_ipm(text, "literal")
    return lit if c == 1.0 else f"{c!r}*({lit})"


def _header(model: dict) -> list[str]:
    md, ap = model["metadata"], model["applicability"]
    inverse = {v: k for k, v in HEADER.items()}
    out = [f"#{inverse[f]}:{md[f]}" for f in ("short_name", "long_name", "revision", "revision_comment", "source")]
    out.append(f"#RevisionDate:{md['revision_date']}")
    out += [f"#{k}:{ap[v]['value']:g}" for k, v in (("InclinationRangeMin", "inc_min"),
                                                     ("InclinationRangeMax", "inc_max"),
                                                     ("AzimuthEWRestriction", "hor_ew_exclusion"))]
    return out


def render(model: dict, libraries: list[dict], envs=None) -> str:
    envs = station_envs() if envs is None else envs
    if "gyro" in model:
        raise IpmError("gyro", None, f"{model['metadata']['model_id']} has gyro survey modes")
    libs = {lib["library_id"].split(":", 1)[0]: lib for lib in libraries}
    lines = _header(model) + [COLUMNS]
    names = {}
    for t in model["terms"]:
        ns, _, key = t["term"].rpartition(":")
        if key.lower() in names:    # IPM names have no namespace and match without regard to case
            raise IpmError("duplicate_name", None, f"{t['term']} and {names[key.lower()]} would be one IPM source")
        names[key.lower()] = t["term"]
        lib = libs[ns or "iscwsa"]
        term = lib["terms"][key]
        wf = lib["weighting_functions"][term["weighting_function"]]
        if "mode" in term:
            raise IpmError("gyro", None, f"{t['term']} is a gyro survey-mode term")
        if term["propagation"] == "Bias":
            raise IpmError("bias", None, f"{t['term']} is a Bias term")
        if term["units"] not in IPM_UNITS:
            raise IpmError(f"unit:{term['units']}", None, t["term"])
        caps = set(term.get("requires", [])) - {"xcl_position_direct"}
        if caps:
            raise IpmError(f"requires:{sorted(caps)[0]}", None, t["term"])
        xcl = "xcl_position_direct" in term.get("requires", [])
        rows = []
        for field, vector in (("depth", "e"), ("inclination", "y" if xcl else "i"), ("azimuth", "x" if xcl else "a")):
            text = canonical(wf[field])
            if text == "0":
                continue
            if xcl and field == "azimuth":          # x is lateral: azimuth * Sin(Inc)
                node = parse(text)
                lateral = (node.left if isinstance(node, Bin) and node.op == "/" and node.right.render() == "Sin(Inc)"
                           else Bin("*", node, Call("Sin", (Var("Inc"),))))
                text = lateral.render()
            try:
                formula = _formula(text, term["units"], field == "depth", envs)
            except IpmError as exc:
                raise IpmError(exc.construct, None, f"{t['term']} {field}") from None
            rows.append(f"{key}\t{vector}\t{TIE[term['propagation']]}\t{IPM_UNITS[term['units']]}\t{t['magnitude']!r}\t{formula}")
        lines += rows
    return "\n".join(lines) + "\n"


def load_libraries(model: dict, root: Path = ROOT) -> list[dict]:
    """The libraries a model pins, read from `root`/library."""
    by_id = {}
    for path in (root / "library").rglob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        by_id[doc["library_id"]] = doc
    return [by_id[ref["id"]] for ref in model["libraries"]]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.json2ipm")
    p.add_argument("model", type=Path)
    p.add_argument("--root", type=Path, default=ROOT)
    a = p.parse_args(argv)
    model = json.loads(a.model.read_text(encoding="utf-8"))
    try:
        text = render(model, load_libraries(model, a.root))
    except IpmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
