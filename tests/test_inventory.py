# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import json
import os
import shutil
from pathlib import Path

import openpyxl
import pytest

from tools.inventory import MODEL_IDS_FILE, ModelId, load_model_ids, owsg_prefix
from tools.sheet import WORKBOOKS_FILE, WorkbookError, read_workbook

WB_DIR = os.environ.get("ISCWSA_WORKBOOKS")
needs_wb = pytest.mark.skipif(not WB_DIR, reason="ISCWSA_WORKBOOKS not set")
COUNTS = {809: 27, 807: 59, 808: 42, 1052: 1}


@pytest.fixture(scope="module")
def workbooks():
    """{iscwsa_file: (entry, sheets, skipped)} for the four known workbooks."""
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    out = {}
    for name, entry in known.items():
        sheets, skipped = read_workbook(Path(WB_DIR) / name)
        out[entry["iscwsa_file"]] = (entry, sheets, skipped)
    return out


@needs_wb
def test_counts(workbooks):
    assert {k: len(v[1]) for k, v in workbooks.items()} == COUNTS
    assert sum(len(v[1]) for v in workbooks.values()) == 129


@needs_wb
def test_non_model_sheets_skipped(workbooks):
    for f in (809, 807, 808):
        assert set(workbooks[f][2]) == {"Index", "Sheet1", "Sheet2"}
    assert workbooks[1052][2] == []


@needs_wb
def test_unreadable_model_sheet_fails(tmp_path):
    name = "iscwsa-mwd-error-models-rev5-23-sep-2022.xlsx"
    copy = tmp_path / name
    shutil.copyfile(Path(WB_DIR) / name, copy)
    wb = openpyxl.load_workbook(copy)
    ws = wb["ISCWSA MWD+SRGM Rev5"]
    for row in ws.iter_rows():
        for c in row:
            if c.value == "Depth Formula":
                c.value = None
    wb.save(copy)
    with pytest.raises(WorkbookError, match="Depth Formula"):
        read_workbook(copy, check=False)


@needs_wb
def test_model_ids_complete_and_unique(workbooks):
    ids = load_model_ids(MODEL_IDS_FILE)
    have = {(f, s.name) for f, (_, sheets, _) in workbooks.items() for s in sheets}
    assert have == set(ids)
    assert len({(m.namespace, m.model_id) for m in ids.values()}) == len(ids) == 129


def test_duplicate_model_id_rejected(tmp_path):
    p = tmp_path / "ids.csv"
    p.write_text(
        "iscwsa_file,sheet,namespace,model_id,library\n"
        "807,MWD+SRGM,generic_iscwsa,A001Mc,iscwsa:rev5\n"
        "808,Other Sheet,generic_iscwsa,A001Mc,iscwsa:rev5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as e:
        load_model_ids(p)
    assert "MWD+SRGM" in str(e.value) and "Other Sheet" in str(e.value)


@needs_wb
def test_ids_match_sheet_prefix(workbooks):
    ids = load_model_ids(MODEL_IDS_FILE)
    checked = 0
    for f, (_, sheets, _) in workbooks.items():
        for s in sheets:
            prefix = owsg_prefix(s)
            if prefix is None:
                continue
            want = f"{prefix}_Fl" if s.name.endswith("_Fl") else str(prefix)
            assert ids[(f, s.name)].model_id == want, (f, s.name)
            checked += 1
    assert checked == 129 - 25


@needs_wb
def test_examples(workbooks):
    ids = load_model_ids(MODEL_IDS_FILE)
    assert ids[(809, "ISCWSA MWD+AX+SAG Rev3_Fl")] == ModelId("iscwsa", "MWD_AX_SAG_Rev3_Fl", "iscwsa:rev3")
    assert ids[(807, "MWD+SRGM_Fl")] == ModelId("generic_iscwsa", "A001Mc_Fl", "iscwsa:rev5")
    rcs = workbooks[1052][1][0]
    assert ids[(1052, "Rot_6Axis_MWD+SRGM")] == ModelId(
        "iscwsa", owsg_prefix(rcs), "iscwsa:rot6axis")


def test_repeated_file_and_sheet_rejected(tmp_path):
    p = tmp_path / "ids.csv"
    p.write_text(
        "iscwsa_file,sheet,namespace,model_id,library\n"
        "807,MWD+SRGM,generic_iscwsa,A001Mc,iscwsa:rev5\n"
        "807,MWD+SRGM,generic_iscwsa,A002Mc,iscwsa:rev5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="MWD"):
        load_model_ids(p)
