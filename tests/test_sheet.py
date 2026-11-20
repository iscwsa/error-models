# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import os
import shutil
from pathlib import Path

import pytest

from tools.extract_xlsx import ExtractError, build_library, parse_param
from tools.sheet import SheetTerm, WorkbookError, read_sheet

WB_DIR = os.environ.get("ISCWSA_WORKBOOKS")
needs_wb = pytest.mark.skipif(not WB_DIR, reason="ISCWSA_WORKBOOKS not set")
MWD = "iscwsa-mwd-error-models-rev5-23-sep-2022.xlsx"
SHEET = "ISCWSA MWD+SRGM Rev5"


@pytest.fixture(scope="module")
def sheet():
    return read_sheet(Path(WB_DIR) / MWD, SHEET)


@needs_wb
def test_read_mwd_srgm_rev5(sheet):
    assert len(sheet.terms) == 35
    assert sheet.meta["OWSG Prefix"] == "A001Mc"
    assert sheet.meta["Revision No"] == 5.1
    assert sheet.meta["Status"] == "Agreed"
    assert sheet.tool_params["XCL Tortuosity"] == "1 deg / 100 ft"
    assert sheet.tool_params["Misalignment Min Course Length"] == "10 m"


@needs_wb
def test_term_row_dbhu(sheet):
    t = next(t for t in sheet.terms if t.code == "DBH-U")
    assert (t.wf_id, t.magnitude, t.units, t.prop) == ("DBH", 2350, "deg.nT", "W")
    assert t.azimuth == "1 / (BField * Cos(Dip))"


@needs_wb
def test_unknown_workbook_refused(tmp_path):
    copy = tmp_path / MWD
    shutil.copyfile(Path(WB_DIR) / MWD, copy)
    with open(copy, "ab") as f:
        f.write(b"\0")
    with pytest.raises(WorkbookError, match="known revisions"):
        read_sheet(copy, SHEET)


def _term(**kw):
    base = dict(no=1, code="T", description="d", wf_id="W", wf_source="s", type="Depth", magnitude=1,
                units="m", prop="W", p1=1, p2=1, p3=0, wf_comment=None, depth="1", inclination="0",
                azimuth="0", sing_north=None, sing_east=None, sing_vert=None)
    base.update(kw)
    return SheetTerm(**base)


def _sheet(terms):
    from tools.sheet import Sheet
    return Sheet("x.xlsx", "0" * 64, "S", {}, {}, terms)


def test_p_flags_mismatch_rejected():
    with pytest.raises(ExtractError, match="P1-P3"):
        build_library("iscwsa:t", [_sheet([_term(prop="R", p1=1)])], [])


def test_parse_param():
    assert parse_param("1 deg / 100 ft") == {"value": 1, "unit": "deg/100ft", "text": "1 deg / 100 ft"}
    assert parse_param("10 m") == {"value": 10, "unit": "m", "text": "10 m"}
    assert parse_param("0 deg") == {"value": 0, "unit": "deg", "text": "0 deg"}
    assert parse_param(3) == {"value": 3, "unit": "-", "text": "3"}
    assert parse_param(0.5)["value"] == 0.5


def test_conflicting_wf_formulas_rejected():
    a, b = _term(code="A"), _term(code="B", depth="2")
    with pytest.raises(ExtractError, match="different formulas"):
        build_library("iscwsa:t", [_sheet([a, b])], [])


def test_stale_erratum_rejected():
    e = {"library": "iscwsa:t", "weighting_function": "W", "field": "depth", "sheet_text": "9",
         "corrected": "2", "source": "s", "reason": "r", "status": "proposed"}
    with pytest.raises(ExtractError, match="stale erratum"):
        build_library("iscwsa:t", [_sheet([_term()])], [e])


@needs_wb
def test_library_dedupes_by_wf_id(sheet):
    lib = build_library("iscwsa:rev5", [sheet], [])
    assert {lib["terms"][c]["weighting_function"] for c in ("DEC-U", "DEC-OS", "DEC-OH", "DEC-OI")} == {"AZ"}
    assert {lib["terms"][c]["weighting_function"] for c in ("DBH-U", "DBH-OS", "DBH-OH", "DBH-OI")} == {"DBH"}
    assert len(lib["weighting_functions"]) < len(lib["terms"])
