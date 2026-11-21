# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Download the ISCWSA workbooks listed in tools/workbooks.json from iscwsa.net and check each against its SHA-256.

Each entry's `iscwsa_file` number is fetched from https://www.iscwsa.net/files/<n>/ and saved under its workbooks.json
name. A file already present with the right hash is not downloaded again. A hash mismatch is an error: ISCWSA has
republished the file, and workbooks.json (and any renamed sheet in tools/model_ids.csv) needs updating.

Usage: python -m tools.fetch_workbooks --out DIR      (then set ISCWSA_WORKBOOKS=DIR)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

WORKBOOKS_FILE = Path(__file__).resolve().parent / "workbooks.json"
URL = "https://www.iscwsa.net/files/{}/"
USER_AGENT = "iscwsa-error-models-fetch/1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(out: Path, workbooks: dict | None = None, opener=urllib.request.urlopen) -> list[str]:
    """Fetch every workbook into `out`; return the error messages (empty when all are present and verified)."""
    workbooks = workbooks if workbooks is not None else json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    for name, entry in workbooks.items():
        dest = out / name
        if dest.is_file() and sha256(dest.read_bytes()) == entry["sha256"]:
            print(f"ok (cached) {name}")
            continue
        url = URL.format(entry["iscwsa_file"])
        with opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as r:
            data = r.read()
        got = sha256(data)
        if got != entry["sha256"]:
            errors.append(f"{name} (iscwsa.net file {entry['iscwsa_file']}): sha256 {got}, expected {entry['sha256']}; "
                          "ISCWSA has republished it, update tools/workbooks.json")
            continue
        dest.write_bytes(data)
        print(f"ok {name}")
    return errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, type=Path, help="folder for the workbooks (ISCWSA_WORKBOOKS)")
    errors = fetch(p.parse_args(argv).out)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
