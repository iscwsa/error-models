# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import hashlib
import json
import re
from pathlib import Path

import pytest

from tools.diagnostics import read_hpt

ROOT = Path(__file__).resolve().parent.parent
VEC = ROOT / "conformance" / "vectors" / "iscwsa_rev5-1"


def vec(n):
    return VEC / f"ErrorModelDiagnostics_Rev5-1_ISCWSA#{n}.dat"


@pytest.mark.parametrize("n,count", [(1, 268), (2, 131), (3, 142)])
def test_station_counts(n, count):
    assert len(read_hpt(vec(n)).stations) == count


def test_well_reference():
    assert read_hpt(vec(1)).well == {"Latitude": 60.0, "BTotal": 50000.0, "Dip": 72.0,
                                     "Declination": -4.0, "GTotal": 9.80665}


def test_first_station_drfr():
    st = read_hpt(vec(1)).stations[0]
    assert st.md == 0.0 and st.mode == "Static"
    assert st.terms["DRFR"][2] == pytest.approx(0.1225)
    assert st.terms["TOTAL"][2] == pytest.approx(0.1225)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_sources_match_model(n):
    model = json.loads((ROOT / "models/iscwsa/A001Mc.json").read_text(encoding="utf-8"))
    lib = json.loads((ROOT / "library/iscwsa/rev5.json").read_text(encoding="utf-8"))["terms"]
    app = model["applicability"]
    src = read_hpt(vec(n)).sources
    assert [s["name"] for s in src] == [t["term"] for t in model["terms"]]
    mode = {"WellByWell": "Well"}
    for s, t in zip(src, model["terms"]):
        lt = lib[t["term"]]
        assert s["units"] == lt["units"], s["name"]
        assert mode.get(s["prop_mode"], s["prop_mode"]) == lt["propagation"], s["name"]
        assert abs(s["magnitude"] - t["magnitude"]) <= 5e-7, s["name"]
        assert s["lower_inc"] == app["inc_min"]["value"]
        assert s["upper_inc"] == app["inc_max"]["value"]


def test_every_station_has_total():
    for n in (1, 2, 3):
        assert all("TOTAL" in s.terms for s in read_hpt(vec(n)).stations)


def test_dat_files_unchanged():
    table = dict(re.findall(r"`(ErrorModelDiagnostics[^`]*\.dat)` \| `([0-9a-f]{64})`",
                            (VEC / "README.md").read_text(encoding="utf-8")))
    assert len(table) == 3
    for name, digest in table.items():
        assert hashlib.sha256((VEC / name).read_bytes()).hexdigest() == digest


def test_manifest_files_exist():
    man = json.loads((ROOT / "conformance/manifest.json").read_text(encoding="utf-8"))
    assert [e["well"] for e in man] == [1, 2, 3]
    for e in man:
        assert e["model"] == "iscwsa:A001Mc"
        assert (ROOT / "conformance" / e["file"]).is_file()
