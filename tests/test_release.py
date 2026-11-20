# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""tools/release.py on a throwaway git repository (never this repository's tags or remote)."""
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from tools import release
from tools.identity import stamp
from tools.release import ReleaseError, check, cut, reopen
from tools.validate import validate_repo

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 26)
FILES = ["library/iscwsa/rev0.json", "models/iscwsa/MWD_Rev0.json", "namespaces.json", ".gitattributes"]


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout


def commit(repo, message="change"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A minimal valid tree (the schemas, one library, one model, a changelog with an Unreleased entry), committed."""
    r = tmp_path / "repo"
    shutil.copytree(ROOT / "schemas", r / "schemas")
    for rel in FILES:
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, r / rel)
    (r / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- First release.\n", encoding="utf-8", newline="\n")
    git(r, "init", "-q")
    commit(r, "init")
    monkeypatch.setattr(release, "determinism", lambda root, workbooks: [])
    return r


def snapshot(repo):
    return {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}


def _cut(repo, version="v0.1.0"):
    return cut(repo, version, TODAY, allow_no_workbooks=True)


def test_repo_is_valid(repo):
    assert validate_repo(repo, registry_check=True) == []


def test_cut_rewrites_urls(repo):
    report = _cut(repo)
    assert report.files_rewritten == 2 + len(list((repo / "schemas").rglob("*.json")))
    for p in (repo / "library").rglob("*.json"):
        assert "/error-models/v0.1.0/schemas/" in json.loads(p.read_text(encoding="utf-8"))["$schema"]
    for p in (repo / "schemas").rglob("*.json"):
        assert "/error-models/v0.1.0/schemas/" in json.loads(p.read_text(encoding="utf-8"))["$id"]
    assert validate_repo(repo, registry_check=True) == []
    log = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased" not in log and "## v0.1.0 (2026-10-26)\n\n- First release.\n" in log
    assert "### Added\n\n- `iscwsa:MWD_Rev0`\n- `iscwsa:rev0`\n" in log
    assert "extract_xlsx --check) was skipped" in log


def test_cut_copies_schemas(repo):
    _cut(repo)
    a = {p.relative_to(repo / "schemas"): p.read_bytes() for p in (repo / "schemas").rglob("*.json")}
    b = {p.relative_to(repo / "tools/schemas/v0.1.0"): p.read_bytes() for p in (repo / "tools/schemas/v0.1.0").rglob("*.json")}
    assert a == b and len(a) > 20


def test_cut_changes_no_hash(repo):
    before = {p: json.loads(p.read_text(encoding="utf-8"))["hash_value"] for p in (repo / "models").rglob("*.json")}
    _cut(repo)
    assert {p: json.loads(p.read_text(encoding="utf-8"))["hash_value"] for p in before} == before


def test_cut_refuses_tampered_hash(repo):
    path = repo / "models/iscwsa/MWD_Rev0.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["terms"][0]["magnitude"] += 1
    path.write_text(json.dumps(doc, indent="\t") + "\n", encoding="utf-8", newline="\n")
    commit(repo)
    with pytest.raises(ReleaseError) as exc:
        _cut(repo)
    assert exc.value.code == "HASH_CHANGED" and "MWD_Rev0" in str(exc.value)


@pytest.mark.parametrize("case, code", [
    ("bad_version", "BAD_VERSION"), ("dirty", "DIRTY"), ("not_valid", "NOT_VALID"), ("empty", "EMPTY_UNRELEASED"),
    ("older", "NOT_NEWER"), ("exists", "EXISTS"), ("no_workbooks", "NO_WORKBOOKS"), ("drift", "NOT_DETERMINISTIC"),
    ("not_main", "NOT_MAIN"),
])
def test_cut_refusals(repo, monkeypatch, case, code):
    version, kw = "v0.1.0", {"allow_no_workbooks": True}
    if case == "bad_version":
        version = "0.1"
    elif case == "dirty":
        (repo / "stray.txt").write_text("x", encoding="utf-8")
    elif case == "not_valid":            # rev5 carries proposed errata
        shutil.copy(ROOT / "library/iscwsa/rev5.json", repo / "library/iscwsa/rev5.json")
        commit(repo)
    elif case == "empty":
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n", encoding="utf-8", newline="\n")
        commit(repo)
    elif case == "older":
        git(repo, "tag", "v0.2.0")
    elif case == "exists":
        git(repo, "tag", "v0.1.0")
    elif case == "no_workbooks":
        kw = {}
    elif case == "drift":
        monkeypatch.setattr(release, "determinism", lambda root, workbooks: ["models/iscwsa/MWD_Rev0.json"])
    elif case == "not_main":
        _cut(repo, "v0.0.1")
        commit(repo)
    before = snapshot(repo)
    with pytest.raises(ReleaseError) as exc:
        cut(repo, version, TODAY, **kw)
    assert exc.value.code == code
    assert snapshot(repo) == before


def test_change_list(repo):
    _cut(repo)
    commit(repo, "release v0.1.0")
    git(repo, "tag", "v0.1.0")
    reopen(repo)
    path = repo / "models/iscwsa/MWD_Rev0.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["terms"][0]["magnitude"] *= 2
    path.write_text(json.dumps(stamp(doc), indent="\t", ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    shutil.copy(ROOT / "models/iscwsa/MWD_AX_Rev0.json", repo / "models/iscwsa/MWD_AX_Rev0.json")
    log = (repo / "CHANGELOG.md").read_text(encoding="utf-8").replace("## Unreleased\n\n", "## Unreleased\n\n- Second.\n\n")
    (repo / "CHANGELOG.md").write_text(log, encoding="utf-8", newline="\n")
    commit(repo)
    report = _cut(repo, "v0.2.0")
    assert (report.added, report.changed, report.removed) == (["iscwsa:MWD_AX_Rev0"], ["iscwsa:MWD_Rev0"], [])
    log = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert log.index("## v0.2.0 (2026-10-26)") < log.index("## v0.1.0 (2026-10-26)")
    assert "### Models and libraries against v0.1.0\n\n### Added\n\n- `iscwsa:MWD_AX_Rev0`\n\n### Changed\n\n- `iscwsa:MWD_Rev0`\n" in log


def test_cut_atomic(repo, monkeypatch):
    before = snapshot(repo)
    calls = {"n": 0}
    real = release.os.replace

    def failing(a, b):
        calls["n"] += 1
        if calls["n"] == 5:
            raise OSError("disk full")
        real(a, b)

    monkeypatch.setattr(release.os, "replace", failing)
    with pytest.raises(OSError):
        _cut(repo)
    assert snapshot(repo) == before
    assert not (repo / "tools").exists()


def test_reopen_round_trip(repo):
    before = snapshot(repo)
    _cut(repo)
    assert reopen(repo) > 0
    after = snapshot(repo)
    strip = lambda s: {k: v for k, v in s.items() if k != "CHANGELOG.md" and not k.startswith("tools/schemas/")}
    assert strip(after) == strip(before)
    log = after["CHANGELOG.md"].decode("utf-8")
    assert log.startswith("# Changelog\n\n## Unreleased\n\n## v0.1.0 (")


def test_reopen_idempotent(repo):
    before = snapshot(repo)
    assert reopen(repo) == 0 and snapshot(repo) == before
    _cut(repo)
    reopen(repo)
    once = snapshot(repo)
    assert reopen(repo) == 0 and snapshot(repo) == once
    assert once["CHANGELOG.md"].decode("utf-8").count("## Unreleased") == 1


def test_check_clean_after_cut(repo):
    _cut(repo)
    assert check(repo, "v0.1.0") == [] and check(repo) == []


def test_check_flags_main_after_cut(repo):
    _cut(repo)
    shutil.copy(ROOT / "models/iscwsa/MWD_AX_Rev0.json", repo / "models/iscwsa/MWD_AX_Rev0.json")
    problems = check(repo)
    assert "models/iscwsa/MWD_AX_Rev0.json: at release main, the tree is at v0.1.0" in problems


def test_check_tag_mismatch(repo):
    _cut(repo)
    assert "the tree is at release v0.1.0, the tag is v0.1.1" in check(repo, "v0.1.1")


def test_check_on_main():
    """This repository between releases: every file at main (the proposed errata are checked only for a release)."""
    assert check(ROOT) == []


def test_rewrite_urls_only_url_keys():
    doc = {"$schema": release.BASE + "main/schemas/model.json", "note": release.BASE + "main/x",
           "p": {"$id": release.BASE + "main/schemas/a.json", "const": release.BASE + "main/schemas/b.json"}}
    out = release.rewrite_urls(doc, "v1.0.0")
    assert out["note"] == doc["note"]
    assert out["$schema"].endswith("/v1.0.0/schemas/model.json") and out["p"]["const"].endswith("/v1.0.0/schemas/b.json")
