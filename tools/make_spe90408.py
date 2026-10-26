# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Write the iscwsa:spe90408 library and the six SPE 90408 Appendix D example models from tools/spe90408.json.

Deterministic: the same source data always gives the same bytes.
Usage: python -m tools.make_spe90408 [ROOT]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.identity import entry_uuid, library_uuid, model_uuid, stamp
from tools.urls import schema_base

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = Path(__file__).resolve().parent / "spe90408.json"
LIBRARY_ID = "iscwsa:spe90408"
LIBRARY_PATH = "library/iscwsa/spe90408.json"
REV5_PATH = "library/iscwsa/rev5.json"
SCHEMA_BASE = schema_base(PACKAGE_ROOT)  # the tree's release (tools/urls.py)
PUBLICATION_DATE = "2004-09-26"  # SPE 90408, presented at the SPE Annual Technical Conference, Houston, September 2004
MODES = {"Table 3": True, "Table 4": True, "Table 6": False, "Table 8": False}  # stationary tables hold at an initialisation


def _text(value: float, unit: str) -> str:
    number = f"{value:g}"
    return number if unit == "-" else f"{number} {unit}"


def _pv(value: float, unit: str, text: str | None = None) -> dict:
    return {"value": value, "unit": unit, "text": text if text is not None else _text(value, unit)}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(doc: dict) -> str:
    return json.dumps(doc, indent="\t", ensure_ascii=False) + "\n"


def build_library(data: dict) -> dict:
    weighting_functions, terms = {}, {}
    for name, spec in data["terms"].items():
        weighting_functions[name] = {
            "depth": spec.get("depth", "0"),
            "inclination": spec.get("inclination", "0"),
            "azimuth": spec.get("azimuth", "0"),
            "source": f"SPE 90408 {spec['table']}",
            "uuid": entry_uuid(LIBRARY_ID, "weighting_function", name),
        }
        term = {
            "description": spec["description"],
            "type": spec["type"],
            "units": spec["units"],
            "propagation": spec["propagation"],
            "weighting_function": name,
            "requires": ["gyro_modes"],
        }
        if spec["table"] in MODES:
            term["mode"] = "continuous" if spec["table"] in ("Table 6", "Table 8") else "stationary"
            term["init"] = MODES[spec["table"]]
        term["uuid"] = entry_uuid(LIBRARY_ID, "term", name)
        terms[name] = term
    return stamp({
        "$schema": SCHEMA_BASE + "library.json",
        "library_id": LIBRARY_ID,
        "uuid": library_uuid(LIBRARY_ID),
        "publisher": "ISCWSA",
        "requires": ["gyro_modes"],
        "weighting_functions": weighting_functions,
        "terms": terms,
        "hash_function": "SHA256",
        "hash_value": "",
    })


def _gyro(spec: dict, speed: float) -> dict:
    def block(b: dict) -> dict:
        return {
            "axes": b["axes"],
            "start_inc": _pv(b["start_inc"], "deg"),
            "end_inc": _pv(b["end_inc"], "deg"),
            "init_inc": _pv(b["init_inc"], "deg") if b["init_inc"] >= 0 else _pv(b["init_inc"], "-", f"{b['init_inc']:g} [Initialised at Surface]"),
        }

    out = {"accelerometer": spec["accelerometer"]}
    if "cant" in spec:
        out["accelerometer_cant"] = _pv(spec["cant"], "deg")
        out["cant_switching"] = spec["cant_switching"]
    if spec.get("external_reference"):
        out["external_reference"] = True
    if "stationary" in spec:
        out["stationary"] = block(spec["stationary"])
    out["continuous"] = [dict(block(b), gyro_speed=_pv(speed, "m/hr")) for b in spec["continuous"]]
    if "min_distance" in spec:
        out["min_distance"] = _pv(spec["min_distance"], "m")
    if "init_factor" in spec:
        out["init_factor"] = _pv(spec["init_factor"], "-")
    return out


def build_model(data: dict, spec: dict, rev5: dict, library: dict) -> dict:
    n = spec["number"]
    name = f"SPE90408_Ex{n}"
    terms = []
    for group in spec["groups"]:
        terms.extend({"term": term, "magnitude": magnitude} for term, magnitude in data["groups"][group])
    return stamp({
        "$schema": SCHEMA_BASE + "model.json",
        "metadata": {
            "model_uuid": model_uuid("iscwsa", name),
            "model_id": f"iscwsa:{name}",
            "short_name": name,
            "long_name": spec["long_name"],
            "revision": "1",
            "revision_date": PUBLICATION_DATE,
            "revision_comment": "Appendix D example model of the paper's generalised gyro error model",
            "source": f"SPE 90408 Appendix D, Example Model #{n}",
            "tool_type": "Gyro",
            "status": "reference",
            "framework": "Other",
            "author": "ISCWSA",
            "tags": ["Example"],
            "application": spec["application"],
            "notes": data["model_notes"],
        },
        "libraries": [
            {"id": rev5["library_id"], "uuid": rev5["uuid"], "hash_value": rev5["hash_value"]},
            {"id": library["library_id"], "uuid": library["uuid"], "hash_value": library["hash_value"]},
        ],
        "applicability": {
            "inc_min": _pv(0, "deg"),
            "inc_max": _pv(spec.get("inc_max", 150), "deg"),
            "hor_ew_exclusion": _pv(0, "deg"),
        },
        "parameters": {"MisalignmentAlt": _pv(3, "-")},
        "gyro": _gyro(spec["gyro"], data["running_speed_m_per_hr"]),
        "terms": terms,
        "hash_function": "SHA256",
        "hash_value": "",
    })


def build(root: Path = PACKAGE_ROOT) -> dict[str, str]:
    """Relative path -> file text, for the library and the six models."""
    data = _read(DATA_FILE)
    rev5 = _read(Path(root) / REV5_PATH)
    library = build_library(data)
    out = {LIBRARY_PATH: _dump(library)}
    for spec in data["models"]:
        out[f"conformance/models/iscwsa/SPE90408_Ex{spec['number']}.json"] = _dump(build_model(data, spec, rev5, library))
    return out


def check(root: Path = PACKAGE_ROOT) -> list[str]:
    """The generated files that differ from the committed ones (missing included), byte for byte."""
    root = Path(root)
    return [rel for rel, text in build(root).items()
            if not (root / rel).is_file() or (root / rel).read_bytes() != text.encode("utf-8")]


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        args = [a for a in args if a != "--check"]
        differ = check(Path(args[0] if args else "."))
        for rel in differ:
            print(f"differs: {rel}")
        return 1 if differ else 0
    root = Path(args[0] if args else ".")
    for rel, text in build(root).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
