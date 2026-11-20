# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Inventory of the ISCWSA workbooks and the fixed (file, sheet) -> model-ID table (tools/model_ids.csv).

The CSV is data, not derived at run time, so a renamed sheet keeps its UUID. `--propose` prints the
model-ID and library proposal, which was reviewed by hand before being committed.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.sheet import WORKBOOKS_FILE, Sheet, read_workbook

MODEL_IDS_FILE = Path(__file__).resolve().parent / "model_ids.csv"
_COLUMNS = ["iscwsa_file", "sheet", "namespace", "model_id", "library"]


@dataclass(frozen=True)
class ModelId:
    namespace: str
    model_id: str
    library: str


def load_model_ids(path: Path = MODEL_IDS_FILE) -> dict[tuple[int, str], ModelId]:
    out: dict[tuple[int, str], ModelId] = {}
    owner: dict[tuple[str, str], tuple[int, str]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (int(row["iscwsa_file"]), row["sheet"])
            if key in out:
                raise ValueError(f"duplicate (file, sheet) row in {path}: file {key[0]}, sheet {key[1]!r}")
            mid = ModelId(row["namespace"], row["model_id"], row["library"])
            qual = (mid.namespace, mid.model_id)
            if qual in owner:
                other = owner[qual]
                raise ValueError(
                    f"duplicate model ID {mid.namespace}:{mid.model_id}: "
                    f"sheet {other[1]!r} (file {other[0]}) and sheet {key[1]!r} (file {key[0]})"
                )
            owner[qual] = key
            out[key] = mid
    return out


def owsg_prefix(sheet: Sheet) -> str | None:
    """The sheet's OWSG Prefix, or None. The 25 obsolete ISCWSA MWD sheets hold the literal text "None"."""
    value = sheet.meta.get("OWSG Prefix")
    if value is None or str(value).strip().lower() in ("", "none"):
        return None
    return str(value).strip()


def propose(iscwsa_file: int, namespace: str, sheet: Sheet) -> ModelId:
    """The model-ID and library proposal."""
    prefix = owsg_prefix(sheet)
    if prefix is not None:
        model_id = prefix
        if sheet.name.endswith("_Fl") and not model_id.endswith("_Fl"):
            model_id += "_Fl"
    else:
        model_id = re.sub(r"[+ ]", "_", re.sub(r"^ISCWSA ", "", sheet.name))
    if iscwsa_file == 1052:
        library = "iscwsa:rot6axis"
    elif iscwsa_file == 809:
        m = re.search(r"Rev(\d)(?:_Fl)?$", sheet.name)
        if not m:
            raise ValueError(f"cannot find the revision in sheet name {sheet.name!r}")
        library = f"iscwsa:rev{m.group(1)}"
    else:
        library = "iscwsa:rev5"
    return ModelId(namespace, model_id, library)


def _scan(workbooks_dir: Path):
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    for name, entry in known.items():
        sheets, _ = read_workbook(Path(workbooks_dir) / name)
        for s in sheets:
            yield entry["iscwsa_file"], entry["namespace"], s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools.inventory")
    ap.add_argument("--workbooks", required=True, type=Path)
    ap.add_argument("--propose", action="store_true", help="print a model_ids.csv proposal and exit")
    args = ap.parse_args(argv)
    scanned = list(_scan(args.workbooks))
    if args.propose:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(_COLUMNS)
        for f, ns, s in scanned:
            m = propose(f, ns, s)
            w.writerow([f, s.name, m.namespace, m.model_id, m.library])
        return 0
    ids = load_model_ids()
    seen = set()
    bad = 0
    for f, _, s in scanned:
        seen.add((f, s.name))
        m = ids.get((f, s.name))
        mapped = f"{m.namespace}:{m.model_id}" if m else "MISSING"
        bad += m is None
        print("\t".join([str(f), s.name, str(owsg_prefix(s)), str(s.meta.get("Revision No")),
                         str(s.meta.get("Status")), mapped]))
    for key in sorted(set(ids) - seen):
        print(f"CSV row has no sheet: {key}", file=sys.stderr)
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
