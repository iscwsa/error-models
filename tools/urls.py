# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The schema URLs of a tree: https://raw.githubusercontent.com/iscwsa/error-models/<release>/schemas/<file>.

<release> is `main` between releases and the release tag (vX.Y.Z) on a cut tree (docs/releasing.md). The generators
(extract_xlsx, make_spe90408, ipm2json) write the release their own tree is at, read from schemas/model.json's $id.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE = "https://raw.githubusercontent.com/iscwsa/error-models/"
_ID_RE = re.compile(re.escape(BASE) + r"([^/]+)/schemas/model\.json$")


def tree_release(root) -> str:
    """The release segment of the tree's schemas/model.json $id ('main' or a tag)."""
    schema_id = json.loads((Path(root) / "schemas" / "model.json").read_text(encoding="utf-8"))["$id"]
    m = _ID_RE.match(schema_id)
    if m is None:
        raise ValueError(f"schemas/model.json $id {schema_id!r} is not {BASE}<release>/schemas/model.json")
    return m.group(1)


def schema_base(root) -> str:
    return f"{BASE}{tree_release(root)}/schemas/"
