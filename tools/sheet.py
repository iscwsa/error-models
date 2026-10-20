# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Reader for the ISCWSA error-model spreadsheets (read-only; workbooks are never modified)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import openpyxl

WORKBOOKS_FILE = Path(__file__).resolve().parent / "workbooks.json"
_HEADER_CELL = "Depth Formula"
_FIRST_TERM_COL = 4  # column D


class WorkbookError(ValueError):
    pass


@dataclass
class SheetTerm:
    no: int
    code: str
    description: str
    wf_id: str
    wf_source: str | None
    type: str
    magnitude: float
    units: str
    prop: str
    p1: float
    p2: float
    p3: float
    wf_comment: str | None
    depth: str | None
    inclination: str | None
    azimuth: str | None
    sing_north: str | None
    sing_east: str | None
    sing_vert: str | None


@dataclass
class Sheet:
    workbook: str
    sha256: str
    name: str
    meta: dict[str, object]
    tool_params: dict[str, object]
    terms: list[SheetTerm]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_workbook(path: Path) -> dict:
    """Return the workbooks.json entry for this file's sha256, or raise WorkbookError."""
    path = Path(path)
    known = json.loads(WORKBOOKS_FILE.read_text(encoding="utf-8"))
    digest = sha256_of(path)
    for name, entry in known.items():
        if entry["sha256"] == digest:
            return {"file_name": name, **entry}
    listing = "; ".join(f"{n} (ISCWSA file {e['iscwsa_file']}, sha256 {e['sha256']})" for n, e in known.items())
    raise WorkbookError(f"{path.name} has unknown sha256 {digest}; known revisions: {listing}")


def _text(value) -> str | None:
    """Cell to verbatim text; numbers via str(), integral floats without the .0."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _label(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.endswith(":"):
        value = value[:-1].rstrip()
    return value or None


def read_sheet(path: Path, sheet: str) -> Sheet:
    path = Path(path)
    check_workbook(path)
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
    try:
        if sheet not in wb.sheetnames:
            raise WorkbookError(f"{path.name} has no sheet {sheet!r}")
        ws = wb[sheet]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()
    header = next(
        (i for i, r in enumerate(rows) if any(c == _HEADER_CELL for c in r[_FIRST_TERM_COL - 1:])), None
    )
    if header is None:
        raise WorkbookError(f"{sheet!r} has no row containing {_HEADER_CELL!r}")
    cols = {str(c).strip(): j for j, c in enumerate(rows[header]) if c is not None and j >= _FIRST_TERM_COL - 1}

    def cell(r, name):
        j = cols[name]
        return r[j] if j < len(r) else None

    meta: dict[str, object] = {}
    tool_params: dict[str, object] = {}
    in_params = False
    history_key = None
    for r in rows:
        a, b = r[0], (r[1] if len(r) > 1 else None)
        label = _label(a)
        if label is None:
            if a is None and b is not None and history_key is not None:
                meta[history_key].append(b)
            continue
        history_key = None
        if isinstance(a, str) and a.strip() == "Tool Parameters":
            in_params = True
            continue
        if not a.strip().endswith(":"):
            continue
        if in_params:
            if b is not None:
                tool_params[label] = b
        elif label == "Revision History":
            meta[label] = [b] if b is not None else []
            history_key = label
        elif b is not None:
            meta[label] = b

    terms = []
    for r in rows[header + 1:]:
        if cell(r, "No") is None:
            break
        terms.append(SheetTerm(
            no=int(cell(r, "No")),
            code=cell(r, "Code"),
            description=cell(r, "Term Description"),
            wf_id=_text(cell(r, "Wt.Fn.")),
            wf_source=cell(r, "Wt.Fn. Source"),
            type=cell(r, "Type"),
            magnitude=cell(r, "Magnitude"),
            units=cell(r, "Units"),
            prop=cell(r, "Prop."),
            p1=cell(r, "P1"), p2=cell(r, "P2"), p3=cell(r, "P3"),
            wf_comment=cell(r, "Wt.Fn. Comment"),
            depth=_text(cell(r, "Depth Formula")),
            inclination=_text(cell(r, "Inclination Formula")),
            azimuth=_text(cell(r, "Azimuth Formula")),
            sing_north=_text(cell(r, "Singularity North Formula")),
            sing_east=_text(cell(r, "Singularity East Formula")),
            sing_vert=_text(cell(r, "Singularity Vert. Formula")),
        ))
    return Sheet(path.name, sha256_of(path), sheet, meta, tool_params, terms)
