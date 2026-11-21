# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""ipm2json on the test fixtures (tests/fixtures/ipm: written from public ISCWSA models or by hand; no vendor file)."""
import json
import shutil
from pathlib import Path

import pytest

from tools.ipm import IpmError, parse_ipm, read_ipm
from tools.ipm2json import ISCWSA_LIBRARY, convert, main, metadata, station_envs, weights_equal
from tools.validate import validate_repo

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "ipm"
REV5 = json.loads(ISCWSA_LIBRARY.read_text(encoding="utf-8"))
FLAGS = {"tool_type": "MWD", "author": "Example Ltd"}


def _convert(path_or_text, ns="example", model_id="X1", library=REV5, **flags):
    ipm = read_ipm(path_or_text) if isinstance(path_or_text, Path) else parse_ipm(path_or_text)
    meta = dict(metadata(ipm.header, dict(FLAGS, **flags)), model_id=model_id)
    return ipm, convert(ipm, ns, meta, library)


def _model(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


HEAD = ("#ShortName:T\n#Description:Test\n#RevisionNumber:1\n#RevisionDate:2026-10-26\n#RevisionComment:t\n"
        "#SourceReference:tests\n#InclinationRangeMin:0\n#InclinationRangeMax:180\n#AzimuthEWRestriction:0\n"
        "Name\tVector\tTie-On\tUnit\tValue\tFormula\n")


def test_matches_iscwsa_terms():
    ipm, (model, vendor, log) = _convert(FIX / "generic_A026Ua.ipm")
    assert vendor is None and model["libraries"] == [{"id": "iscwsa:rev5", "uuid": REV5["uuid"], "hash_value": REV5["hash_value"]}]
    assert model["terms"] == _model("models/generic_iscwsa/A026Ua.json")["terms"]
    assert all(":" not in t["term"] for t in model["terms"])
    assert weights_equal(model, [REV5], ipm)


def test_same_name_different_formula():
    """A vendor XYM3 without the Abs of the ISCWSA one is a vendor term, and the log says why."""
    text = HEAD + "XYM3\ti\ts\td\t0.1\tcos(inc)*cos(azt)\nXYM3\ta\ts\td\t0.1\t-cos(inc)*sin(azt)/sin(inc)\n"
    ipm, (model, vendor, log) = _convert(text)
    assert [t["term"] for t in model["terms"]] == ["example:XYM3"]
    assert "XYM3" in vendor["terms"] and any("not iscwsa:XYM3: inclination formula" in line for line in log)
    assert weights_equal(model, [REV5, vendor], ipm)


def test_numeric_match_and_opposite_sign():
    """Text that differs but gives the library's weights over the whole Inc / AzT range matches the ISCWSA term:
    XYM1 as Sin(Inc) (the library's Abs(Sin(Inc))), XYM2 on the lateral vector with the opposite sign."""
    text = HEAD + "XYM1\ti\ts\td\t0.1\tsin(inc)\nXYM2\tl\ts\td\t0.1\tsin(inc)\n"
    ipm, (model, vendor, log) = _convert(text)
    assert vendor is None and [t["term"] for t in model["terms"]] == ["XYM1", "XYM2"]
    assert "XYM1: iscwsa:XYM1 (numeric match (inclination text differs))" in log
    assert "XYM2: iscwsa:XYM2 (numeric match, opposite sign (azimuth text differs))" in log
    assert weights_equal(model, [REV5], ipm)


def test_vendor_term_written():
    ipm, (model, vendor, log) = _convert(FIX / "example_vendor.ipm")
    assert [t["term"] for t in model["terms"]] == ["DRFR", "DSFS", "example:XGYRO", "example:XMIS"]
    assert vendor["library_id"] == "example:X1_terms" and set(vendor["terms"]) == {"XGYRO", "XMIS"}
    assert vendor["extends"] == model["libraries"][:1]
    assert vendor["terms"]["XGYRO"]["units"] == "deg/hr" and vendor["terms"]["XMIS"]["propagation"] == "Global"
    assert vendor["weighting_functions"]["XGYRO"]["azimuth"] == "Sin(AzT) / (EarthRate * Cos(Lat) * Cos(Inc))"
    assert "XGYRO: same_as iscwsa:GXY-B1S" in log
    assert weights_equal(model, [REV5, vendor], ipm)


def test_lateral_vertical_limit():
    """An `l` row is an azimuth weight over Sin(Inc); at the vertical stations of the 806 wells its lateral limit equals
    the IPM row."""
    text = HEAD + "XLAT\tl\ts\td\t0.2\t-cos(inc)*cos(azt)\n"
    ipm, (model, vendor, log) = _convert(text)
    wf = vendor["weighting_functions"]["XLAT"]
    assert wf["azimuth"] == "-Cos(Inc) * Cos(AzT) / Sin(Inc)"
    assert (wf["singularity_north"], wf["singularity_east"], wf["singularity_vertical"]) == (
        "-(-Cos(Inc) * Cos(AzT)) * Sin(AzT)", "-Cos(Inc) * Cos(AzT) * Cos(AzT)", "0")
    assert any(e["Inc"] == 0.0 for e in station_envs())
    assert weights_equal(model, [REV5, vendor], ipm)
    wrong = json.loads(json.dumps(model))
    wrong["terms"][0]["magnitude"] = 0.21
    assert not weights_equal(wrong, [REV5, vendor], ipm)


def test_depth_units_fold():
    """Feet: a dimensionally consistent row reads naturally in metres; one that is not keeps the exact factor."""
    text = HEAD + "XDEP\te\ts\t-\t0.001\ttmd\nXODD\te\ts\t-\t0.001\ttmd*tmd\n"
    ipm, (model, vendor, log) = _convert(text)
    wf = vendor["weighting_functions"]
    assert wf["XDEP"]["depth"] == "MD"
    assert wf["XODD"]["depth"] == "0.3048 * (MD * 3.280839895013123 * (MD * 3.280839895013123))"
    assert weights_equal(model, [REV5, vendor], ipm)


def test_missing_metadata_named():
    ipm = read_ipm(FIX / "example_vendor.ipm")
    header = {k: v for k, v in ipm.header.items() if k != "RevisionDate"}
    with pytest.raises(IpmError) as exc:
        metadata(header, FLAGS)
    assert exc.value.construct == "missing:revision_date"
    with pytest.raises(IpmError) as exc:
        metadata(ipm.header, {"tool_type": "MWD"})
    assert exc.value.construct == "missing:author"


@pytest.mark.parametrize("row, construct", [
    ("XSW\ti\ts\td\t0.1\tswon(inc-0.5)", "function:SWON"),
    ("XD\ti\ts\td\t0.1\tsqrt(dmd)", "constant:dmd"),
    ("XR\ti\ts\td\t0.1\t1\t0\t45", "range"),
    ("XR\tq\ts\td\t0.1\t1", "vector:q"),
    ("XR\ti\ts\tdph\t0.1\t1", "unit:dph"),
])
def test_untranslatable_rows(row, construct):
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "DRFR\te\tr\tm\t0.35\t1\n" + row + "\n")
    assert exc.value.construct == construct


def test_variables_convert():
    """Plain variables are inlined (docs/ipm.md, "Variables"); `azi` is AzT; an unused variable is ignored, even one
    that accumulates; `erot` through a variable still gives deg/hr."""
    text = HEAD + ("w_a\tn\tn\t-\t1\tsin(inc)\nw_b\tn\tn\t-\t1\tsqrt(1-(w_a)^2)\n"
                   "acc\tn\tn\t-\t1\tacc+smd\n"
                   "XM3\ti\ts\td\t0.1\tcos(azi)*w_b\nXM3\tl\ts\td\t0.1\t-sin(azi)*w_b\n"
                   "r\tn\tn\t-\t1\t1/erot\nXG\ta\ts\td\t0.1\tsin(azt)*r/cos(inc)\n")
    ipm, (model, vendor, log) = _convert(text)
    assert [t["term"] for t in model["terms"]] == ["example:XM3", "example:XG"]
    wf = vendor["weighting_functions"]
    assert wf["XM3"]["inclination"] == "Cos(AzT) * Sqrt(1 - Sin(Inc) ^ 2)"
    assert vendor["terms"]["XG"]["units"] == "deg/hr"
    assert wf["XG"]["azimuth"] == "Sin(AzT) * (1 / (EarthRate * Cos(Lat))) / Cos(Inc)"
    assert weights_equal(model, [REV5, vendor], ipm)


@pytest.mark.parametrize("rows, construct", [
    ("acc\tn\tn\t-\t1\tacc+smd\nXA\ti\ts\td\t0.1\tacc", "variable:persistent"),   # accumulates
    ("XA\ti\ts\td\t0.1\tk\nk\tn\tn\t-\t1\tsin(inc)", "variable:persistent"),      # used before its definition
    ("k\tn\tn\t-\t1\t0\nk\tn\tn\t-\t1\tk+1\nXA\ti\ts\td\t0.1\tk", "variable:redefined"),
    ("k\tn\tn\t-\t1\tsin(inc)\t0\t45\nXA\ti\ts\td\t0.1\tk", "range"),
    ("k\tn\tn\td\t1\tinc\nXA\ti\ts\td\t0.1\tk", "variable:unit"),
    ("inc\tn\tn\t-\t1\t1", "name"),
])
def test_variables_refused(rows, construct):
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "DRFR\te\tr\tm\t0.35\t1\n" + rows + "\n")
    assert exc.value.construct == construct


def test_no_rows():
    """Column titles with no rows are a zero-error tool; a file without the layout's titles is refused."""
    _, (model, vendor, _) = _convert(HEAD)
    assert model["terms"] == [] and vendor is None
    other = HEAD.replace("Name\tVector", "Name\t\tVector")      # another program's export: shifted columns
    with pytest.raises(IpmError) as exc:
        _convert(other + "XR\t\ti\ts\td\t0.1\t1\n")
    assert exc.value.construct == "no_rows"


def test_repeated_and_mixed_vectors():
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "XR\ti\ts\td\t0.1\t1\nXR\ty\ts\td\t0.1\t1\n")
    assert exc.value.construct == "repeated_vector"
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "XR\ti\ts\td\t0.1\t1\nXR\te\ts\tm\t0.1\t1\n")
    assert exc.value.construct == "mixed_vectors"


def test_subsea_rows():
    text = HEAD + "XD\te\ts\tm\t1\t1\nXD\ts\ts\tm\t2\t1\n"
    _, (land, _, _) = _convert(text)
    ipm = parse_ipm(text)
    sea = convert(ipm, "example", dict(metadata(ipm.header, FLAGS), model_id="X1"), REV5, subsea=True)[0]
    assert land["terms"][0]["magnitude"] == 1 and sea["terms"][0]["magnitude"] == 2


def _args(path, out):
    return ["--namespace", "example", "--model-id", "X1", "--tool-type", "MWD", "--author", "Example Ltd",
            str(path), "--out", str(out)]


def test_no_partial_output(tmp_path):
    bad = tmp_path / "bad.ipm"
    bad.write_text(HEAD + "XGYRO\ta\ts\td\t0.1\t1\nXSW\ti\ts\td\t0.1\tswon(inc)\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    assert main(_args(bad, out)) == 1
    assert list(out.iterdir()) == []


def test_output_validates(tmp_path):
    out = tmp_path / "out"
    assert main(_args(FIX / "example_vendor.ipm", out)) == 0
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*.json")) == [
        "library/example/X1_terms.json", "models/example/X1.json"]
    shutil.copytree(ROOT / "library" / "iscwsa", out / "library" / "iscwsa")
    problems = [p for p in validate_repo(out) if "example" in p.file]
    assert problems == []


# ---------------------------------------------------------------- review findings
def test_zero_first_value():
    """The magnitude is the first non-zero Value; a zero row adds nothing."""
    ipm, (model, vendor, _) = _convert(HEAD + "Q\ti\tg\td\t0\tsin(inc)\nQ\ta\tg\td\t0.1\tcos(inc)\n")
    assert model["terms"][0]["magnitude"] == 0.1 and vendor["weighting_functions"]["Q"]["inclination"] == "0"
    assert weights_equal(model, [REV5, vendor], ipm)


@pytest.mark.parametrize("line", ["R\tia\ts\td\t5\tsin(inc)", "S\ti\ts\td\t5", "N\ti\ts\td\tnan\t1"])
def test_bad_row_is_not_dropped(line):
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "DRFR\te\tr\tm\t0.35\t1\n" + line + "\n")
    assert exc.value.construct == "syntax"


def test_negative_value_and_snapping():
    ipm, (model, vendor, _) = _convert(HEAD + "XN\te\tr\tm\t-0.35\t1\nXT\te\ts\tt\t0.56\ttmd\n")
    assert vendor["weighting_functions"]["XN"]["depth"] == "-1"
    assert [t["magnitude"] for t in model["terms"]] == [0.35, 0.00056]
    assert weights_equal(model, [REV5, vendor], ipm)


def test_colon_in_name():
    with pytest.raises(IpmError) as exc:
        _convert(HEAD + "A:B\ti\ts\td\t0.1\t1\n")
    assert exc.value.construct == "name"


def test_write_failure_leaves_nothing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "library").write_text("not a directory", encoding="utf-8")
    assert main(_args(FIX / "example_vendor.ipm", out)) == 1
    assert sorted(p.name for p in out.rglob("*")) == ["library"]
