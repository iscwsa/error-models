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


def test_changelog_lists_every_erratum():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased" in changelog
    for e in json.loads((ROOT / "tools" / "errata.json").read_text(encoding="utf-8")):
        row = f"`{e['library']}` {e['weighting_function']} {e['field']}"
        assert row in changelog, row
        assert e["status"] in changelog


def test_xcla_reason_has_no_stale_wording():
    assert "finding under review" not in (ROOT / "tools" / "errata.json").read_text(encoding="utf-8")
