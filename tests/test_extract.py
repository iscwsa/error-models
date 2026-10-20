# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import json
import os
import shutil
from pathlib import Path

import pytest

from tools.extract_xlsx import main
from tools.sheet import read_sheet
from tools.validate import validate_repo

WB_DIR = os.environ.get("ISCWSA_WORKBOOKS")
pytestmark = pytest.mark.skipif(not WB_DIR, reason="ISCWSA_WORKBOOKS not set")
SHEET = "ISCWSA MWD+SRGM Rev5"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    path = tmp_path_factory.mktemp("repo")
    shutil.copyfile(ROOT / "namespaces.json", path / "namespaces.json")
    assert main(["--workbooks", WB_DIR, "--sheet", SHEET, "--library", "iscwsa:rev5", "--out", str(path)]) == 0
    return path


def test_generated_files_validate(out):
    # REQUIRES_MISMATCH ignored until Task 5 makes the extractor attach per-term requires
    problems = [p for p in validate_repo(out, registry_check=True) if p.code != "REQUIRES_MISMATCH"]
    assert {p.code for p in problems} == {"ERRATA_PROPOSED"}
    assert len(problems) == 6   # XYM3E, XYM4E (2 fields each), XCLA singularity north and east


def test_model_magnitudes_round_trip(out):
    model = json.loads((out / "models/iscwsa/A001Mc.json").read_text(encoding="utf-8"))
    sheet = read_sheet(Path(WB_DIR) / "iscwsa-mwd-error-models-rev5-23-sep-2022.xlsx", SHEET)
    assert [(t["term"], t["magnitude"]) for t in model["terms"]] == [(t.code, t.magnitude) for t in sheet.terms]
    assert model["metadata"]["model_id"] == "iscwsa:A001Mc"
    assert model["parameters"]["XCLTortuosity"] == {"value": 1, "unit": "deg/100ft", "text": "1 deg / 100 ft"}
    assert "approved" not in model["metadata"]


def test_output_is_deterministic(out, tmp_path):
    shutil.copyfile(ROOT / "namespaces.json", tmp_path / "namespaces.json")
    main(["--workbooks", WB_DIR, "--sheet", SHEET, "--library", "iscwsa:rev5", "--out", str(tmp_path)])
    for rel in ("library/iscwsa/rev5.json", "models/iscwsa/A001Mc.json"):
        assert (out / rel).read_bytes() == (tmp_path / rel).read_bytes()


def test_errata_applied(out):
    lib = json.loads((out / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))
    wf = lib["weighting_functions"]["XYM3E"]
    assert wf["inclination"] == "Abs(Cos(Inc)) * Cos(AzT) * Max(1, Sqrt(10 / (MD - MDPrev)))"
    assert {e["field"] for e in wf["errata"]} == {"inclination", "azimuth"}
    assert all(e["status"] == "proposed" for e in wf["errata"])
