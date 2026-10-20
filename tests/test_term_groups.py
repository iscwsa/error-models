# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""tools/term_groups.json against the schema and (when available) the published workbooks."""
import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

from tests.test_schemas import errors
from tools.inventory import _scan, load_model_ids

ROOT = Path(__file__).resolve().parent.parent
GROUPS = json.loads((ROOT / "tools" / "term_groups.json").read_text(encoding="utf-8"))
LIBRARIES = {f"iscwsa:rev{n}" for n in range(6)} | {"iscwsa:rot6axis"}
PAIRS = (
    "ABX/ABY ABIX/ABIY ASX/ASY ASIX/ASIY MBX/MBY MBIX/MBIY MSX/MSY MSIX/MSIY MX/MY "
    "ABXY-TI1S/ABXY-TI2S ABIXY-TI1S/ABIXY-TI2S ASXY-TI1S/ASXY-TI2S ASIXY-TI1S/ASIXY-TI2S "
    "MBXY-TI1S/MBXY-TI2S MBIXY-TI1S/MBIXY-TI2S MSXY-TI1S/MSXY-TI2S MSIXY-TI1S/MSIXY-TI2S "
    "GXY-B1R/GXY-B2R GXY-B1S/GXY-B2S CNA/CNI XYM1/XYM2 XYM3/XYM4 XYM3E/XYM4E XCLA/XCLH "
    "ROT-AN1/ROT-AN2 ROT-CA1/ROT-CA2 ROT-DSC1/ROT-DSC2"
).split()
CO_OCCUR = "co-occur with equal magnitude and propagation in every published sheet (iscwsa.net files 807, 808, 809, 1052)"


def test_keys_are_the_seven_libraries():
    assert set(GROUPS) == LIBRARIES


def test_every_group_is_schema_valid_and_pairs_are_from_the_list():
    seen = set()
    for lib, groups in GROUPS.items():
        for g in groups:
            assert errors("term_group.json", g) == []
            assert "/".join(g["terms"]) in PAIRS
            assert g["source"].endswith(CO_OCCUR)
            seen.add("/".join(g["terms"]))
    assert seen == set(PAIRS)


def test_family_sources():
    by_pair = {"/".join(g["terms"]): g["source"] for groups in GROUPS.values() for g in groups}
    assert by_pair["XYM3E/XYM4E"] == "Definition of the ISCWSA Error Model Rev5.13 §5.1.2; " + CO_OCCUR
    assert by_pair["XCLA/XCLH"] == "§5.2.1; " + CO_OCCUR
    assert by_pair["ABXY-TI1S/ABXY-TI2S"].startswith("Rev 3 toolface-independent x/y terms, Definition Rev5.13 §6.3.4; ")
    assert by_pair["CNA/CNI"] == CO_OCCUR


@pytest.mark.skipif(not os.environ.get("ISCWSA_WORKBOOKS"), reason="ISCWSA_WORKBOOKS not set")
def test_groups_match_workbooks():
    ids = load_model_ids()
    terms_of = defaultdict(list)
    for f, _, sheet in _scan(Path(os.environ["ISCWSA_WORKBOOKS"]).expanduser()):
        terms_of[ids[(f, sheet.name)].library].append({t.code for t in sheet.terms})
    assert set(terms_of) == LIBRARIES
    for lib, sheets in terms_of.items():
        present = set().union(*sheets)
        listed = {"/".join(g["terms"]) for g in GROUPS[lib]}
        expected = {p for p in PAIRS if set(p.split("/")) <= present}
        assert listed == expected, lib
        for pair in PAIRS:  # the all-pairs claim: never one member without the other, in any sheet
            a, b = pair.split("/")
            assert all((a in s) == (b in s) for s in sheets), (lib, pair)
