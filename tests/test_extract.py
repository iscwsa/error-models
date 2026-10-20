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


# ---- Task 4: parameters, status and framework for every sheet ----
from tools.extract_xlsx import PARAM_NAMES, ExtractError, build_library, build_model, parse_param  # noqa: E402
from tools.inventory import ModelId, load_model_ids  # noqa: E402
from tools.sheet import WORKBOOKS_FILE, read_workbook  # noqa: E402


def test_parse_param_bool():
    assert parse_param("True") == {"value": True, "unit": "-", "text": "True"}
    assert parse_param("False") == {"value": False, "unit": "-", "text": "False"}
    assert parse_param(True) == {"value": True, "unit": "-", "text": "True"}


def test_parse_param_initialised_at_surface():
    text = "-1 [Initialised at Surface]"
    assert parse_param(text) == {"value": -1, "unit": "-", "text": text}


@pytest.fixture(scope="module")
def all_sheets():
    """[(iscwsa_file, Sheet)] for all 129 model sheets."""
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    out = []
    for name, entry in known.items():
        sheets, _ = read_workbook(Path(WB_DIR) / name)
        out += [(entry["iscwsa_file"], s) for s in sheets]
    return out


def test_param_names_cover_all_sheets(all_sheets):
    assert len(all_sheets) == 129
    labels = {k for _, s in all_sheets for k in s.tool_params}
    assert labels - set(PARAM_NAMES) == set()


def test_unknown_param_label_rejected(all_sheets):
    f, sheet = all_sheets[0]
    mid = load_model_ids()[(f, sheet.name)]
    lib = {"library_id": mid.library, "uuid": "u", "hash_value": "h"}
    sheet.tool_params["Bogus Label"] = "1 m"
    try:
        with pytest.raises(ExtractError, match="Bogus Label"):
            build_model(sheet, mid, lib, set())
    finally:
        del sheet.tool_params["Bogus Label"]


def _build(f, sheet, ids, lib=None):
    mid = ids[(f, sheet.name)]
    lib = lib or {"library_id": mid.library, "uuid": "u", "hash_value": "h"}
    return build_model(sheet, mid, lib, {f"{i.namespace}:{i.model_id}" for i in ids.values()})


def test_status_mapping(all_sheets):
    ids = load_model_ids()
    obsolete = 0
    for f, s in all_sheets:
        meta = _build(f, s, ids)["metadata"]
        if f == 1052:
            assert meta["status"] == "candidate"
            assert meta["sheet_status"] == "Agreed"
            assert meta["framework"] == "ISCWSA RCS"
        elif s.meta["Status"] == "Obsolete":
            obsolete += 1
            assert meta["status"] == "superseded"
        else:
            assert meta["status"] == "current"
    assert obsolete == 25


def test_status_unknown_rejected(all_sheets):
    ids = load_model_ids()
    f, s = next((f, s) for f, s in all_sheets if f == 807)
    old = s.meta["Status"]
    s.meta["Status"] = "Draft"
    try:
        with pytest.raises(ExtractError, match="Draft"):
            _build(f, s, ids)
    finally:
        s.meta["Status"] = old


def test_framework_follows_library(all_sheets):
    ids = load_model_ids()
    for f, s in all_sheets:
        meta = _build(f, s, ids)["metadata"]
        lib = ids[(f, s.name)].library
        assert meta["framework"] == ("ISCWSA RCS" if lib == "iscwsa:rot6axis" else "ISCWSA Rev" + lib[-1])


def test_gyro_ct_parameters(all_sheets):
    f, s = next((f, s) for f, s in all_sheets if s.name == "GYRO-NS-CT")
    p = _build(f, s, load_model_ids())["parameters"]
    assert p["RunningSpeed"]["value"] == 2743.2 and p["RunningSpeed"]["unit"] == "m/hr"
    assert p["NoiseReductionFactor"]["value"] == 0.4082
    assert p["XYContinuousGyro"]["value"] is True
    assert p["StartInc"] == {"value": 15, "unit": "deg", "text": "15 deg"}


def test_supersedes_only_repo_ids(all_sheets):
    ids = load_model_ids()
    known = {f"{i.namespace}:{i.model_id}" for i in ids.values()}
    for f, s in all_sheets:
        meta = _build(f, s, ids)["metadata"]
        for key in ("supersedes", "superseded_by"):
            assert set(meta.get(key, [])) <= known
        if s.meta.get("Replaces / Replaced By"):
            assert meta["replaces_text"] == s.meta["Replaces / Replaced By"]


def test_parameter_value_schema_allows_boolean():
    schema = json.loads((ROOT / "schemas/parameter_value.json").read_text(encoding="utf-8"))
    assert {"type": "boolean"} in schema["properties"]["value"]["anyOf"]


def test_a001mc_unchanged(out):
    """Regenerating iscwsa:A001Mc matches the committed file (framework excepted, if it changed)."""
    committed = ROOT / "models/iscwsa/A001Mc.json"
    if not committed.exists():
        pytest.skip("no committed A001Mc")
    new = (out / "models/iscwsa/A001Mc.json").read_bytes()
    old = committed.read_bytes()
    if new != old:   # only `framework` (and the hash it feeds) may differ
        n, o = json.loads(new), json.loads(old)
        assert n["metadata"].pop("framework") != o["metadata"].pop("framework")
        n.pop("hash_value"), o.pop("hash_value")
        assert n == o
