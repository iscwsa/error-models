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
    problems = validate_repo(out, registry_check=True)
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
    """Regenerating iscwsa:A001Mc matches the committed file except the library hash (rev5 gained term requires)."""
    committed = ROOT / "models/iscwsa/A001Mc.json"
    if not committed.exists():
        pytest.skip("no committed A001Mc")
    n = json.loads((out / "models/iscwsa/A001Mc.json").read_bytes())
    o = json.loads(committed.read_bytes())
    for doc in (n, o):
        doc.pop("hash_value")
        doc["libraries"][0].pop("hash_value")   # Task 6 regenerates the committed model against the new rev5
    assert n == o


# ---- Task 5: every library ----
import subprocess  # noqa: E402

from tools.extract_xlsx import PROP, TERM_REQUIRES_FILE, build_libraries  # noqa: E402

COUNTS = {   # (terms, weighting functions) per library: the 2026-10-20 probe
    "iscwsa:rev0": (36, 33), "iscwsa:rev1": (38, 35), "iscwsa:rev2": (38, 35), "iscwsa:rev3": (41, 39),
    "iscwsa:rev4": (43, 39), "iscwsa:rev5": (96, 59), "iscwsa:rot6axis": (38, 27),
}
ROT_TERMS = ("ROT-AMXY-PS ROT-AN1 ROT-AN2 ROT-ANZ ROT-ASXY ROT-AXY-ATTEN ROT-CA1 ROT-CA2 ROT-DSC1 ROT-DSC2 "
             "ROT-EDDY ROT-MSXY ROT-MXY-ATTEN").split()


@pytest.fixture(scope="module")
def libraries(all_sheets):
    ids = load_model_ids()
    by_lib: dict[str, list] = {}
    for f, s in all_sheets:
        by_lib.setdefault(ids[(f, s.name)].library, []).append(s)
    errata = json.loads((ROOT / "tools/errata.json").read_text(encoding="utf-8"))
    groups = json.loads((ROOT / "tools/term_groups.json").read_text(encoding="utf-8"))
    log: list[str] = []
    return build_libraries(by_lib, errata, groups, log=log), log


def test_libraries_build(libraries):
    libs, _ = libraries
    assert set(libs) == set(COUNTS)
    for lib_id, (n_terms, n_wfs) in COUNTS.items():
        lib = libs[lib_id]
        assert (len(lib["terms"]), len(lib["weighting_functions"])) == (n_terms, n_wfs), lib_id
        assert lib["library_id"] == lib_id
        assert "extends" not in lib
    assert set(ROT_TERMS) <= set(libs["iscwsa:rot6axis"]["terms"])
    assert not set(ROT_TERMS) & set(libs["iscwsa:rev5"]["terms"])


def test_rot6axis_keeps_its_own_text(libraries):
    libs, _ = libraries
    assert libs["iscwsa:rot6axis"]["weighting_functions"]["ABXY-TI2"]["singularity_north"] == "-Sin(AzM) / GField"
    assert libs["iscwsa:rev5"]["weighting_functions"]["ABXY-TI2"]["singularity_north"] == "-Sin(Az) / GField"


def test_every_group_defined(libraries, tmp_path):
    libs, _ = libraries
    for lib_id, lib in libs.items():
        assert lib["term_groups"], lib_id
        for g in lib["term_groups"]:
            assert set(g["terms"]) <= set(lib["terms"]), (lib_id, g)
    shutil.copyfile(ROOT / "namespaces.json", tmp_path / "namespaces.json")
    for lib_id, lib in libs.items():
        write_json_lib(tmp_path, lib_id, lib)
    codes = {p.code for p in validate_repo(tmp_path, registry_check=True)}
    assert "GROUP_UNKNOWN_TERM" not in codes
    assert codes <= {"ERRATA_PROPOSED"}


def write_json_lib(root, lib_id, lib):
    from tools.extract_xlsx import write_json
    write_json(root / "library" / "iscwsa" / f"{lib_id.partition(':')[2]}.json", lib)


def test_requires_per_term(libraries):
    libs, _ = libraries
    spec = json.loads(TERM_REQUIRES_FILE.read_text(encoding="utf-8"))
    gyro = "AXYZ-MIS AXYZ-SF AXYZ-ZB DSTS EXT-REF GXY-B1R GXY-B1S GXY-B2R GXY-B2S GXY-G1 GXY-G4 GXY-GD GXY-GRW GXY-RN GZ-GD".split()
    assert {t for t, caps in spec.items() if caps == ["gyro_modes"]} == set(gyro)
    assert spec["DSTB"] == ["bias_terms"] and spec["AMIB"] == ["bias_terms"]
    assert spec["XCLA"] == ["xcl_position_direct"] and spec["XCLH"] == ["xcl_position_direct"]
    rev5 = libs["iscwsa:rev5"]
    assert set(rev5["requires"]) == {"xcl_position_direct", "gyro_modes"}
    assert rev5["terms"]["XCLA"]["requires"] == ["xcl_position_direct"]
    assert all(rev5["terms"][t]["requires"] == ["gyro_modes"] for t in gyro)
    assert all("requires" not in t for c, t in rev5["terms"].items() if c not in spec)
    for lib in libs.values():
        assert set(lib["requires"]) == {c for t in lib["terms"].values() for c in t.get("requires", [])}
    assert libs["iscwsa:rev0"]["requires"] == ["bias_terms"] or "bias_terms" in libs["iscwsa:rev0"]["requires"]


def test_gyro_terms_are_gyro_only(all_sheets):
    spec = json.loads(TERM_REQUIRES_FILE.read_text(encoding="utf-8"))
    gyro_terms, other_terms = set(), set()
    for _, s in all_sheets:
        (gyro_terms if s.meta["Tool Type"] == "Gyro" else other_terms).update(t.code for t in s.terms)
    assert gyro_terms - other_terms == {t for t, caps in spec.items() if caps == ["gyro_modes"]}


def test_bias_propagation():
    assert PROP["B"] == "Bias"
    schema = json.loads((ROOT / "schemas/library_term.json").read_text(encoding="utf-8"))
    assert "Bias" in schema["properties"]["propagation"]["enum"]


def test_extractor_log_lists_wf_conflicts(libraries):
    _, log = libraries
    assert all(isinstance(line, str) for line in log)
    assert all(("wf_comment" in line or "wf_source" in line) for line in log)


def test_library_id_must_match_model(all_sheets):
    ids = load_model_ids()
    f, s = all_sheets[0]
    lib = {"library_id": "iscwsa:rev9", "uuid": "u", "hash_value": "h"}
    with pytest.raises(ExtractError, match="rev9"):
        build_model(s, ids[(f, s.name)], lib, set())


def _strip(entry):
    return {k: v for k, v in entry.items() if k not in ("requires", "hash_value")}


def test_rev5_unchanged_for_a001mc(libraries, all_sheets):
    libs, _ = libraries
    old = json.loads(subprocess.run(["git", "show", "c82dbaf:library/iscwsa/rev5.json"], cwd=ROOT, check=True,
                                    capture_output=True).stdout.decode("utf-8"))
    ids = load_model_ids()
    sheet = next(s for f, s in all_sheets if ids[(f, s.name)].model_id == "A001Mc" and ids[(f, s.name)].namespace == "iscwsa")
    new = libs["iscwsa:rev5"]
    assert new["hash_value"] != old["hash_value"]
    used_terms = {t.code for t in sheet.terms}
    assert used_terms
    for code in used_terms:
        assert _strip(new["terms"][code]) == _strip(old["terms"][code]), code
        wf = old["terms"][code]["weighting_function"]
        assert _strip(new["weighting_functions"][wf]) == _strip(old["weighting_functions"][wf]), wf
