# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""json2ipm, and the round trips through ipm2json (docs/ipm.md)."""
import collections
import json
from pathlib import Path

import pytest

from tools.ipm import IpmError, parse_ipm
from tools.ipm2json import ISCWSA_LIBRARY, convert, metadata, weights_equal
from tools.json2ipm import load_libraries, render

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "ipm"
REV5 = json.loads(ISCWSA_LIBRARY.read_text(encoding="utf-8"))
CARRIED = ("short_name", "long_name", "revision", "revision_date", "revision_comment", "source")


def _model(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _fixture_text(name):
    """The fixture without its first line (the comment saying how it was written)."""
    return (FIX / name).read_text(encoding="utf-8").split("\n", 1)[1]


def _back(model, libraries, ns=None):
    """render, then ipm2json against the model's own ISCWSA library."""
    ipm = parse_ipm(render(model, libraries))
    mns, _, name = model["metadata"]["model_id"].partition(":")
    md = model["metadata"]
    meta = dict(metadata(ipm.header, {"tool_type": md["tool_type"], "author": md["author"]}), model_id=name)
    iscwsa = next(lib for lib in libraries if lib["library_id"].startswith("iscwsa:"))
    return ipm, convert(ipm, ns or mns, meta, iscwsa)


@pytest.mark.parametrize("rel, fixture", [("models/iscwsa/MWD_Rev4.json", "iscwsa_MWD_Rev4.ipm"),
                                          ("models/generic_iscwsa/A026Ua.json", "generic_A026Ua.ipm")])
def test_render_fixture(rel, fixture):
    m = _model(rel)
    assert render(m, load_libraries(m)) == _fixture_text(fixture)


@pytest.mark.parametrize("rel, construct", [
    ("models/generic_iscwsa/A001Mc.json", "variable:XCLTortuosity"),
    ("models/iscwsa/MWD_bias_Rev0.json", "bias"),
    ("models/generic_iscwsa/A021Gc.json", "gyro"),
])
def test_refuses(rel, construct):
    m = _model(rel)
    with pytest.raises(IpmError) as exc:
        render(m, load_libraries(m))
    assert exc.value.construct == construct


def test_round_trip_json_ipm_json():
    """Every model render accepts comes back with the same terms, magnitudes, libraries and carried metadata. 27 of the
    129 are accepted; the others need XCLTortuosity (89), gyro modes (10) or bias terms (3)."""
    accepted, refused = [], collections.Counter()
    for path in sorted((ROOT / "models").rglob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        libs = load_libraries(m)
        try:
            ipm, (back, vendor, _) = _back(m, libs)
        except IpmError as exc:
            refused[exc.construct] += 1
            continue
        accepted.append(m["metadata"]["model_id"])
        assert vendor is None, m["metadata"]["model_id"]
        assert back["terms"] == m["terms"] and back["libraries"] == m["libraries"], m["metadata"]["model_id"]
        assert {f: back["metadata"][f] for f in CARRIED} == {f: m["metadata"][f] for f in CARRIED}
        assert {k: v["value"] for k, v in back["applicability"].items()} == {
            k: v["value"] for k, v in m["applicability"].items()}
        assert weights_equal(back, libs, ipm)
    assert len(accepted) == 27
    assert dict(refused) == {"variable:XCLTortuosity": 89, "gyro": 10, "bias": 3}


@pytest.mark.parametrize("fixture", ["iscwsa_MWD_Rev4.ipm", "generic_A026Ua.ipm", "example_vendor.ipm"])
def test_round_trip_ipm_json_ipm(fixture):
    """IPM -> JSON -> IPM gives the fixture's rows (name, vector, tie-on, unit, value, formula) back unchanged."""
    ipm = parse_ipm(_fixture_text(fixture))
    library = REV5 if "Rev4" not in fixture else json.loads((ROOT / "library/iscwsa/rev4.json").read_text(encoding="utf-8"))
    meta = dict(metadata(ipm.header, {"tool_type": "MWD", "author": "Example Ltd"}), model_id="X1")
    model, vendor, _ = convert(ipm, "example", meta, library)
    libs = [library] + ([vendor] if vendor else [])
    again = parse_ipm(render(model, libs))
    key = lambda r: (r.name.upper(), r.vector, r.tie_on, r.unit, r.value, r.formula)
    assert [key(r) for r in again.rows] == [key(r) for r in ipm.rows]


def test_namespace_change():
    """Through json2ipm and back under another namespace: the iscwsa references and every magnitude are unchanged;
    only the vendor terms move to the new namespace."""
    ipm = parse_ipm(_fixture_text("example_vendor.ipm"))
    meta = dict(metadata(ipm.header, {"tool_type": "MWD", "author": "Example Ltd"}), model_id="X1")
    model, vendor, _ = convert(ipm, "example", meta, REV5)
    _, (other, other_vendor, _) = _back(model, [REV5, vendor], ns="other")
    assert [t["magnitude"] for t in other["terms"]] == [t["magnitude"] for t in model["terms"]]
    assert [t["term"] for t in other["terms"]] == [t["term"].replace("example:", "other:") for t in model["terms"]]
    assert other_vendor["library_id"] == "other:X1_terms"
    assert other_vendor["weighting_functions"]["XGYRO"]["azimuth"] == vendor["weighting_functions"]["XGYRO"]["azimuth"]


def test_x_rows_round_trip():
    """A vendor x row comes back as the same x row (lateral, defined at a vertical station)."""
    head = _fixture_text("example_vendor.ipm").split("Name\t", 1)[0] + "Name\tVector\tTie-On\tUnit\tValue\tFormula\n"
    ipm = parse_ipm(head + "XC\tx\ts\td\t1\tcos(inc)\nXC\ty\ts\td\t1\tsin(inc)\n")
    meta = dict(metadata(ipm.header, {"tool_type": "MWD", "author": "Example Ltd"}), model_id="X1")
    model, vendor, _ = convert(ipm, "example", meta, REV5)
    again = parse_ipm(render(model, [REV5, vendor]))
    assert [(r.vector, r.formula) for r in again.rows] == [("y", "sin(inc)"), ("x", "cos(inc)")]


def test_duplicate_ipm_names_refused():
    ipm = parse_ipm(_fixture_text("example_vendor.ipm"))
    meta = dict(metadata(ipm.header, {"tool_type": "MWD", "author": "Example Ltd"}), model_id="X1")
    model, vendor, _ = convert(ipm, "example", meta, REV5)
    vendor = json.loads(json.dumps(vendor))
    vendor["terms"]["DRFR"] = dict(vendor["terms"]["XMIS"])
    model["terms"].append({"term": "example:DRFR", "magnitude": 1.0})
    with pytest.raises(IpmError) as exc:
        render(model, [REV5, vendor])
    assert exc.value.construct == "duplicate_name"
