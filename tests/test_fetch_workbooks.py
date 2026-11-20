# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""tools.fetch_workbooks without the network: a fake opener serves the bytes."""
import io

from tools.fetch_workbooks import fetch, sha256

GOOD = b"published workbook"
WORKBOOKS = {"a.xlsx": {"sha256": sha256(GOOD), "iscwsa_file": 1}}


def opener_serving(data, calls):
    def opener(req, timeout):
        calls.append(req.full_url)
        return io.BytesIO(data)
    return opener


def test_downloads_and_verifies(tmp_path):
    calls = []
    assert fetch(tmp_path, WORKBOOKS, opener_serving(GOOD, calls)) == []
    assert (tmp_path / "a.xlsx").read_bytes() == GOOD
    assert calls == ["https://www.iscwsa.net/files/1/"]


def test_cached_file_is_not_downloaded(tmp_path):
    (tmp_path / "a.xlsx").write_bytes(GOOD)
    calls = []
    assert fetch(tmp_path, WORKBOOKS, opener_serving(b"", calls)) == []
    assert calls == []


def test_republished_file_is_an_error_and_not_saved(tmp_path):
    errors = fetch(tmp_path, WORKBOOKS, opener_serving(b"republished", []))
    assert len(errors) == 1 and "republished" in errors[0] and "a.xlsx" in errors[0]
    assert not (tmp_path / "a.xlsx").exists()
