# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The IPM parser and the formula translation (docs/ipm.md)."""
import json
from pathlib import Path

import pytest

from tools.formula import canonical
from tools.ipm import IpmError, IpmRow, parse_ipm, read_ipm, to_ipm, translate, variables

ROOT = Path(__file__).resolve().parent.parent
SNIPPET = (
    "#Name: Example snippet, written by hand\n"
    "#Description: four rows of the guide's layout\n"
    "Name\tVector\tTie-On\tUnit\tValue\tFormula\n"
    "dsf\te\ts\t-\t0.00056\ttmd\n"
    "mx\ti\ts\td\t0.1\tsin(inc)\n"
    "mx\tl\ts\td\t0.1\t-cos(inc)*cos(azt)\n"
    "drf\te\tr\tm\t0.35\t1\t0\t0\n"
)


def test_parse_rows():
    f = parse_ipm(SNIPPET)
    assert f.header == {"Name": "Example snippet, written by hand", "Description": "four rows of the guide's layout"}
    assert f.rows == [
        IpmRow("dsf", "e", "s", "-", 0.00056, "tmd", None, None, 4),
        IpmRow("mx", "i", "s", "d", 0.1, "sin(inc)", None, None, 5),
        IpmRow("mx", "l", "s", "d", 0.1, "-cos(inc)*cos(azt)", None, None, 6),
        IpmRow("drf", "e", "r", "m", 0.35, "1", None, None, 7),
    ]


def test_translate_constants():
    assert translate("sqrt(10/(smd/mtf))") == "Sqrt(10 / (MD - MDPrev))"
    assert translate("cos(inc)*cos(azt)") == "Cos(Inc) * Cos(AzT)"
    assert translate("SIN(Inc)/GTOT") == "Sin(Inc) / GField"
    assert translate("erot", "natural") == "EarthRate * Cos(Lat)"
    assert translate("erot") == "3600 * EarthRate * Cos(Lat)"
    assert translate("tmd") == "MD * 3.280839895013123"
    assert translate("tmd", "natural") == "MD"
    assert translate("tmd*tvd/mtf", "natural") == "MD * TVD"
    assert translate("sqrt(10/smd)", "natural") == "Sqrt(10 / (MD - MDPrev))"
    assert translate("mtf/smd", "natural") == "1 / (MD - MDPrev)"
    assert translate("din+daz") == "Inc - IncPrev + (AzT - AzPrev)"
    assert translate("dtr*pi*tho") == "RAD * Pi * 0.001"
    assert translate("cos(azi)") == "Cos(AzT)"


VARS = ("Name\tVector\tTie-On\tUnit\tValue\tFormula\n"
        "k1\tn\tn\t-\t1\tsin(inc)\n"
        "k2\tn\tn\t-\t2\tsqrt(1-(K1)^2)\n"
        "q\tl\ts\td\t0.1\t-sin(azi)*k2\n")


def test_variables_inlined():
    """A use of a plain variable becomes Value * (its formula), in the reading of the row that uses it."""
    f = parse_ipm(VARS)
    var = variables(f.rows)
    assert set(var) == {"k1", "k2"}
    row = f.rows[-1]
    assert translate(row.formula, variables=var, row=row) == "-Sin(AzT) * (2 * Sqrt(1 - Sin(Inc) ^ 2))"
    assert translate("k1*smd", "natural", var, row) == "Sin(Inc) * (MD - MDPrev)"


def _library_formulas():
    lib = json.loads((ROOT / "library" / "iscwsa" / "rev5.json").read_text(encoding="utf-8"))
    for key, wf in lib["weighting_functions"].items():
        for fld in ("depth", "inclination", "azimuth"):
            yield key, fld, wf[fld]


def test_to_ipm_inverse():
    """Every rev5 formula `to_ipm` accepts comes back unchanged; the refused ones are pinned with their reason."""
    refused = {}
    for key, fld, text in _library_formulas():
        try:
            back = to_ipm(text)
        except IpmError as exc:
            refused[f"{key}/{fld}"] = exc.construct
            continue
        assert translate(back, "natural") == canonical(text), (key, fld, back)
    assert refused == {
        "XCLA/azimuth": "variable:XCLTortuosity",
        "XCLH/inclination": "variable:XCLTortuosity",
        "GXY-RN/azimuth": "variable:NoiseReductionFactor",
        "GXY-GD/azimuth": "variable:XY_Gyro_Drift",
        "GXY-GRW/azimuth": "variable:XY_Gyro_Random_Walk",
        "GZ-GD/azimuth": "variable:Z_Gyro_Drift",
    }


@pytest.mark.parametrize("formula, construct", [
    ("swon(inc - 0.5)", "function:SWON"),
    ("ln(tmd)", "function:LN"),
    ("dog", "constant:dog"),
    ("sqrt(dmd)", "constant:dmd"),
    ("sin(inc)cos(inc)", "syntax"),
    ("2^3^2", "syntax"),
])
def test_untranslatable_names_construct(formula, construct):
    with pytest.raises(IpmError) as exc:
        translate(formula)
    assert exc.value.construct == construct


def test_encodings(tmp_path):
    utf8 = tmp_path / "a.ipm"
    utf8.write_bytes(SNIPPET.encode("utf-8"))
    crlf = tmp_path / "b.ipm"
    crlf.write_bytes(SNIPPET.replace("\n", "\r\n").replace("by hand", "by hand °").encode("cp1252"))
    bom = tmp_path / "c.ipm"
    bom.write_bytes(b"\xef\xbb\xbf" + SNIPPET.encode("utf-8"))
    a, b, c = read_ipm(utf8), read_ipm(crlf), read_ipm(bom)
    assert a.rows == b.rows == c.rows and a.header == c.header
    assert b.header["Name"].endswith("°")
    binary = tmp_path / "d.ipm"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    with pytest.raises(IpmError) as exc:
        read_ipm(binary)
    assert exc.value.construct == "binary"
