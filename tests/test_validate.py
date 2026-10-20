# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Tests for tools/validate.py, one per problem code."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from tools.identity import entry_uuid, library_uuid, model_uuid, stamp
from tools.validate import main, validate_repo

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TAG_BASE = "https://raw.githubusercontent.com/iscwsa/error-models/{}/schemas/"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_library(mutate=None, library_id="iscwsa:rev5"):
    lib = _fixture("minimal_library.json")
    lib["library_id"] = library_id
    lib["uuid"] = library_uuid(library_id)
    for section, kind in (("weighting_functions", "weighting_function"), ("terms", "term")):
        for key, entry in lib[section].items():
            entry["uuid"] = entry_uuid(library_id, kind, key)
    if mutate:
        mutate(lib)
    return stamp(lib)


def make_model(lib, mutate=None, model_id="iscwsa:minimal"):
    model = _fixture("minimal_model.json")
    ns, _, name = model_id.partition(":")
    model["metadata"]["model_id"] = model_id
    model["metadata"]["model_uuid"] = model_uuid(ns, name)
    model["libraries"] = [{"id": lib["library_id"], "uuid": lib["uuid"], "hash_value": lib["hash_value"]}]
    if mutate:
        mutate(model)
    return stamp(model)


def write(root, rel, doc):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc, indent="\t"), encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    shutil.copy(ROOT / "namespaces.json", tmp_path / "namespaces.json")
    lib = make_library()
    write(tmp_path, "library/iscwsa/rev5.json", lib)
    write(tmp_path, "models/iscwsa/minimal.json", make_model(lib))
    return tmp_path


def codes(root, **kw):
    return sorted({p.code for p in validate_repo(root, **kw)})


def edit(root, rel, fn, restamp=True):
    path = root / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(stamp(doc) if restamp else doc, indent="\t"), encoding="utf-8")


def test_clean_fixture_repo_has_no_problems(repo):
    assert validate_repo(repo, registry_check=True) == []


def test_missing_data_folders_are_fine(tmp_path):
    assert validate_repo(tmp_path) == []


def test_unparseable_json_is_schema_problem(repo):
    write(repo, "models/iscwsa/broken.json", "{not json")
    problems = validate_repo(repo)
    assert [p.code for p in problems] == ["SCHEMA"]
    assert "cannot parse" in problems[0].detail


def test_schema_violation(repo):
    edit(repo, "models/iscwsa/minimal.json", lambda d: d.update(extra=1))
    assert codes(repo) == ["SCHEMA"]


def test_unknown_release(repo):
    def go(d):
        d["$schema"] = TAG_BASE.format("v9.9") + "model.json"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["UNKNOWN_RELEASE"]


def test_unknown_schema_host(repo):
    edit(repo, "models/iscwsa/minimal.json", lambda d: d.update({"$schema": "https://example.com/model.json"}))
    assert codes(repo) == ["UNKNOWN_RELEASE"]


def test_release_mismatch(repo):
    # A bundled v1.0 schema set, copied from main with ids/consts rewritten.
    src, dst = ROOT / "schemas", repo / "tools" / "schemas" / "v1.0"
    for path in src.rglob("*.json"):
        out = dst / path.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(path.read_text(encoding="utf-8").replace("/main/schemas/", "/v1.0/schemas/"), encoding="utf-8")

    def go(d):
        d["$schema"] = TAG_BASE.format("v1.0") + "model.json"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["RELEASE_MISMATCH"]


def test_hand_edited_magnitude_is_hash_problem(repo):
    def go(d):
        d["terms"][0]["magnitude"] = 0.99
    edit(repo, "models/iscwsa/minimal.json", go, restamp=False)
    assert codes(repo) == ["HASH"]


def test_edited_library_is_library_hash_problem(repo):
    def go(d):
        d["terms"]["DREF"]["description"] = "Changed"
    edit(repo, "library/iscwsa/rev5.json", go)  # restamped, so only the model's pin is stale
    assert codes(repo) == ["LIBRARY_HASH"]


def test_entry_hash(repo):
    def go(d):
        d["terms"]["DREF"]["description"] = "Changed"
    edit(repo, "library/iscwsa/rev5.json", go, restamp=False)
    assert "ENTRY_HASH" in codes(repo)


def test_library_top_level_hash(repo):
    def go(d):
        d["publisher"] = "Other"
    edit(repo, "library/iscwsa/rev5.json", go, restamp=False)
    assert "HASH" in codes(repo)


def test_uuid(repo):
    def go(d):
        d["metadata"]["model_uuid"] = "00000000-0000-4000-8000-0000000000ff"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["UUID"]


def test_library_entry_uuid(repo):
    def go(d):
        d["weighting_functions"]["DREF"]["uuid"] = "00000000-0000-4000-8000-0000000000ff"
    edit(repo, "library/iscwsa/rev5.json", go)
    assert "UUID" in codes(repo)


def test_library_missing(repo):
    (repo / "library" / "iscwsa" / "rev5.json").unlink()
    assert codes(repo) == ["LIBRARY_MISSING"]


def test_term_missing(repo):
    def go(d):
        d["terms"][0]["term"] = "NOPE"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["TERM_MISSING"]


def test_prefixed_term_in_other_namespace_found(repo):
    other = make_library(library_id="owsg:extra")
    write(repo, "library/owsg/extra.json", other)

    def go(d):
        d["libraries"].append({"id": "owsg:extra", "uuid": other["uuid"], "hash_value": other["hash_value"]})
        d["terms"].append({"term": "owsg:DREF", "magnitude": 0.1})
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == []


def test_unprefixed_term_not_found_in_non_iscwsa_library(repo):
    other = make_library(library_id="owsg:extra")
    write(repo, "library/owsg/extra.json", other)
    (repo / "library" / "iscwsa" / "rev5.json").unlink()

    def go(d):
        d["libraries"] = [{"id": "owsg:extra", "uuid": other["uuid"], "hash_value": other["hash_value"]}]
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["TERM_MISSING"]


def test_wf_missing(repo):
    def go(d):
        d["terms"]["DREF"]["weighting_function"] = "NOPE"
    edit(repo, "library/iscwsa/rev5.json", go)
    assert "WF_MISSING" in codes(repo)


def test_duplicate_term(repo):
    def go(d):
        d["terms"].append(copy.deepcopy(d["terms"][0]))
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["DUPLICATE_TERM"]


def test_duplicate_library_key(repo):
    path = repo / "library" / "iscwsa" / "rev5.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"terms": {', '"terms": {"DREF": {}, ', 1), encoding="utf-8")
    assert "DUPLICATE_TERM" in codes(repo)


@pytest.mark.parametrize("field,text", [("depth", "Foo(1)"), ("inclination", "1 +"), ("azimuth", "Unknown * 2")])
def test_formula(repo, field, text):
    def go(d):
        d["weighting_functions"]["DREF"][field] = text
    edit(repo, "library/iscwsa/rev5.json", go)
    assert "FORMULA" in codes(repo)


def test_formula_in_errata_corrected(repo):
    def go(d):
        d["weighting_functions"]["DREF"]["errata"] = [
            {"field": "depth", "sheet_text": "1", "corrected": "Bad(", "source": "x", "reason": "y", "status": "accepted"}
        ]
    edit(repo, "library/iscwsa/rev5.json", go)
    assert "FORMULA" in codes(repo)


def test_namespace_syntax_reported_once_without_schema(repo):
    (repo / "library" / "iscwsa" / "rev5.json").unlink()
    lib = make_library(library_id="BH:rev5")
    write(repo, "library/bh/rev5.json", lib)
    problems = validate_repo(repo)
    assert [p.code for p in problems if p.file == "library/bh/rev5.json"] == ["NAMESPACE_SYNTAX"]


def test_namespace_unregistered_only_with_registry(repo):
    lib = make_library(library_id="zzz:rev5")
    write(repo, "library/zzz/rev5.json", lib)
    assert codes(repo) == []
    problems = validate_repo(repo, registry_check=True)
    assert [(p.code, p.file) for p in problems] == [("NAMESPACE_UNREGISTERED", "library/zzz/rev5.json")]


def _proposed(d):
    d["terms"]["DREF"]["errata"] = [
        {"field": "units", "sheet_text": "deg", "corrected": "m", "source": "x", "reason": "y", "status": "proposed"}
    ]


def test_errata_proposed_reported(repo):
    edit(repo, "library/iscwsa/rev5.json", _proposed)
    problems = validate_repo(repo)
    assert {p.code for p in problems} >= {"ERRATA_PROPOSED"}


def test_errata_proposed_exit_codes(repo, capsys):
    path = repo / "library" / "iscwsa" / "rev5.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    _proposed(doc)
    doc = stamp(doc)
    path.write_text(json.dumps(doc, indent="\t"), encoding="utf-8")
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["libraries"][0].update(hash_value=doc["hash_value"]))
    assert main([str(repo)]) == 0
    assert "warning:" in capsys.readouterr().out
    assert main(["--release", str(repo)]) == 1


def test_cli_exit_codes(repo, capsys):
    assert main(["--registry", str(repo)]) == 0
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["terms"][0].update(magnitude=0.99), restamp=False)
    assert main([str(repo)]) == 1
    assert "HASH" in capsys.readouterr().out


def test_this_repository_is_clean():
    # proposed errata are warnings until the user decides; anything else is a failure
    # REQUIRES_MISMATCH is tolerated only until Task 5 regenerates library/iscwsa/rev5.json with per-term requires
    assert {p.code for p in validate_repo(ROOT, registry_check=True)} <= {"ERRATA_PROPOSED", "REQUIRES_MISMATCH"}


def test_dotdot_release_tag_is_unknown_release(repo):
    def go(d):
        d["$schema"] = TAG_BASE.format("..") + "model.json"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["UNKNOWN_RELEASE"]


def test_tag_dir_missing_schema_files_is_unknown_release(repo):
    (repo / "tools" / "schemas" / "v2.0").mkdir(parents=True)
    (repo / "tools" / "schemas" / "v2.0" / "library.json").write_text("{}", encoding="utf-8")

    def go(d):
        d["$schema"] = TAG_BASE.format("v2.0") + "model.json"
    edit(repo, "models/iscwsa/minimal.json", go)
    assert codes(repo) == ["UNKNOWN_RELEASE"]


def test_duplicate_library_id(repo):
    shutil.copy(repo / "library" / "iscwsa" / "rev5.json", repo / "library" / "iscwsa" / "rev5_copy.json")
    problems = validate_repo(repo)
    assert [(p.code, p.file) for p in problems] == [("DUPLICATE_LIBRARY", "library/iscwsa/rev5_copy.json")]


def test_duplicate_non_term_key_is_duplicate_key(repo):
    path = repo / "library" / "iscwsa" / "rev5.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"publisher"', '"publisher": "x", "publisher"', 1), encoding="utf-8")
    assert [p.code for p in validate_repo(repo) if p.file.startswith("library/")] == ["DUPLICATE_KEY"]


def test_duplicate_weighting_function_key_is_duplicate_term(repo):
    path = repo / "library" / "iscwsa" / "rev5.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"weighting_functions": {', '"weighting_functions": {"DREF": {}, ', 1), encoding="utf-8")
    assert [p.code for p in validate_repo(repo) if p.file.startswith("library/")] == ["DUPLICATE_TERM"]


def test_wf_and_term_same_key_have_distinct_uuids(repo):
    lib = json.loads((repo / "library" / "iscwsa" / "rev5.json").read_text(encoding="utf-8"))
    assert lib["weighting_functions"]["DREF"]["uuid"] != lib["terms"]["DREF"]["uuid"]
    assert validate_repo(repo) == []


def test_bad_registry_reported_once(repo):
    (repo / "namespaces.json").write_text("{bad", encoding="utf-8")
    problems = validate_repo(repo, registry_check=True)
    assert [(p.code, p.file) for p in problems] == [("SCHEMA", "namespaces.json")]


def _code_list(root):
    return [p.code for p in validate_repo(root)]


def test_requires_union(repo):
    def go(d):
        d["terms"]["DREF"]["requires"] = ["gyro_modes"]
    edit(repo, "library/iscwsa/rev5.json", go)
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["libraries"][0].update(hash_value=json.loads((repo / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["hash_value"]))
    assert _code_list(repo) == ["REQUIRES_MISMATCH"]


def test_requires_union_satisfied(repo):
    def go(d):
        d["terms"]["DREF"]["requires"] = ["gyro_modes"]
        d["requires"] = ["gyro_modes"]
    edit(repo, "library/iscwsa/rev5.json", go)
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["libraries"][0].update(hash_value=json.loads((repo / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["hash_value"]))
    assert _code_list(repo) == []


def test_incomplete_group(repo):
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["terms"].pop())
    assert _code_list(repo) == ["INCOMPLETE_GROUP"]


def test_group_unused_is_fine(repo):
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["terms"].__delitem__(slice(1, None)))
    assert _code_list(repo) == []


def test_group_magnitude_mismatch(repo):
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["terms"][-1].update(magnitude=0.3))
    assert _code_list(repo) == ["GROUP_MISMATCH"]


def test_group_propagation_mismatch(repo):
    def go(d):
        d["terms"]["PB"]["propagation"] = "Systematic"
    edit(repo, "library/iscwsa/rev5.json", go)
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["libraries"][0].update(hash_value=json.loads((repo / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["hash_value"]))
    assert _code_list(repo) == ["GROUP_MISMATCH"]


def test_group_unknown_term(repo):
    def go(d):
        d["term_groups"][0]["terms"] = ["PA", "NOPE"]
    edit(repo, "library/iscwsa/rev5.json", go)
    edit(repo, "models/iscwsa/minimal.json", lambda d: d["libraries"][0].update(hash_value=json.loads((repo / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["hash_value"]))
    assert _code_list(repo) == ["GROUP_UNKNOWN_TERM"]


def test_group_qualified_members_resolve(repo):
    def go(d):
        d["term_groups"][0]["terms"] = ["iscwsa:PA", "PB"]
    edit(repo, "library/iscwsa/rev5.json", go)
    edit(repo, "models/iscwsa/minimal.json", lambda d: (d["libraries"][0].update(hash_value=json.loads((repo / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["hash_value"]), d["terms"].pop()))
    assert _code_list(repo) == ["INCOMPLETE_GROUP"]


def test_ambiguous_term(repo):
    def strip(d):
        del d["terms"]["PA"], d["terms"]["PB"], d["term_groups"]
    other = make_library(strip, library_id="iscwsa:rev4")
    write(repo, "library/iscwsa/rev4.json", other)
    edit(repo, "models/iscwsa/minimal.json",
         lambda d: d["libraries"].append({"id": "iscwsa:rev4", "uuid": other["uuid"], "hash_value": other["hash_value"]}))
    problems = validate_repo(repo)
    assert [p.code for p in problems] == ["AMBIGUOUS_TERM"]
    assert "DREF" in problems[0].detail
