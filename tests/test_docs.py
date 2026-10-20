# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The README status table and the changelog against the files they describe."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _table_ids():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("### MODEL STATUS", 1)[1].split("\n---", 1)[0]
    return [m.group(1) for m in re.finditer(r"^\| `([^`]+)` \|", section, re.M)]


def test_status_table_lists_every_model():
    ids = _table_ids()
    on_disk = set()
    for path in (ROOT / "models").glob("*/*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        on_disk.add(doc["metadata"]["model_id"])
    assert len(ids) == 129
    assert len(set(ids)) == 129
    assert set(ids) == on_disk


def test_status_table_counts():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("### MODEL STATUS", 1)[1].split("\n---", 1)[0]
    rows = [r for r in section.splitlines() if r.startswith("| `")]
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    assert sum(1 for c in cells if c[4] == "loaded") == 111
    assert sum(1 for c in cells if c[4] == "refused") == 18
    assert sum(1 for c in cells if c[7] == "19476/19476") == 2


def test_changelog_lists_every_erratum():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased" in changelog
    for e in json.loads((ROOT / "tools" / "errata.json").read_text(encoding="utf-8")):
        row = f"| `{e['library']}` {e['weighting_function']} {e['field']} | {e['status']} |"
        assert row in changelog, row


def test_no_internal_names_or_stale_wording():
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", *(ROOT / "docs").glob("*.md")]
    for f in files:
        assert not re.search(r"\b(Plan|Task) \d", f.read_text(encoding="utf-8")), f
    assert "finding under review" not in (ROOT / "tools" / "errata.json").read_text(encoding="utf-8")
