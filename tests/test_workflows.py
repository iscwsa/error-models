# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The CI workflows (no YAML library in the requirements: line checks)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _runs(name):
    return [ln.strip()[len("- run: "):] for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("- run: ")]


def test_workflows_parse():
    """Both files are plain block YAML: no tabs, and every key line is `key:` or `- item`."""
    for name in ("validate.yml", "release.yml"):
        for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines():
            assert "\t" not in ln, (name, ln)
            s = ln.strip()
            assert not s or s.startswith(("#", "- ")) or ":" in s, (name, ln)
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "  push:\n    tags:\n      - \"v*\"\n" in text and "pull_request" not in text and "branches" not in text
    assert "permissions:\n  contents: read\n" in text
    assert _runs("release.yml")[-1] == 'python -m tools.release check --tag "${{ github.ref_name }}"'


def test_validate_yml_steps():
    assert _runs("validate.yml") == [
        "pip install -r tools/requirements.txt",
        "python -m tools.fetch_workbooks --out .workbooks",
        "pytest",
        "python -m tools.validate --registry .",
        "python -m tools.extract_xlsx --workbooks .workbooks --all --check",
        "python -m tools.make_spe90408 --check",
        "python -m tools.release check",
    ]


def test_validate_yml_workbooks_and_triggers():
    """The workbook tests run in CI (cached published workbooks), and a branch push doesn't run CI twice with its PR."""
    text = (WORKFLOWS / "validate.yml").read_text(encoding="utf-8")
    assert "  push:\n    branches: [main]\n" in text
    assert "ISCWSA_WORKBOOKS: ${{ github.workspace }}/.workbooks" in text
    assert "key: workbooks-${{ hashFiles('tools/workbooks.json') }}" in text
