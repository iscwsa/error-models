# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import hashlib
import json
import re
from pathlib import Path

import pytest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tools.diagnostics import read_hpt, read_vectors, tolerance

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
@pytest.mark.parametrize("model_path", ["models/iscwsa/A001Mc.json", "models/generic_iscwsa/A001Mc.json"])
def test_sources_match_model(n, model_path):
    model = json.loads((ROOT / model_path).read_text(encoding="utf-8"))
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
    per_term = [e for e in man if e["kind"] == "per_term_nev"]
    assert [(e["model"], e["well"]) for e in per_term] == [
        (m, w) for m in ("iscwsa:A001Mc", "generic_iscwsa:A001Mc") for w in (1, 2, 3)]
    assert len({e["file"] for e in per_term}) == 3
    assert {e["kind"] for e in man} == {"per_term_nev", "total_nev", "hla"}
    for e in man:
        assert (ROOT / "conformance" / e["file"]).is_file()


T3 = ROOT / "conformance/vectors/spe67616/table3.json"
AE = ROOT / "conformance/vectors/spe90408/appendix_e.json"


def _schema_validator():
    registry = Registry()
    for path in sorted((ROOT / "schemas").rglob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012))
    schema = json.loads((ROOT / "schemas" / "vectors.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


@pytest.mark.parametrize("path", [T3, AE])
def test_vector_files_validate(path):
    assert list(_schema_validator().iter_errors(json.loads(path.read_text(encoding="utf-8")))) == []


def test_vector_schema_rejects_bad_vectors():
    doc = json.loads(T3.read_text(encoding="utf-8"))
    doc["cases"][0]["results"][0]["sigma_hla"] = [1.0, 2.0]
    assert list(_schema_validator().iter_errors(doc))
    doc = json.loads(AE.read_text(encoding="utf-8"))
    doc["kind"] = "nonsense"
    assert list(_schema_validator().iter_errors(doc))


def test_vector_counts():
    t3 = read_vectors(T3)
    assert t3.kind == "hla"
    assert len(t3.cases) == 4 and sum(len(c["results"]) for c in t3.cases) == 6
    assert t3.inputs == {"tie_on": "zero_uncertainty", "toolface": "borehole"}
    assert [len(c["legs"]) for c in t3.cases] == [1, 1, 1, 3]
    ae = read_vectors(AE)
    assert ae.kind == "total_nev"
    count = {}
    for c in ae.cases:
        n = sum(len(r["nev"]) for r in c["results"])
        count[c["model"]] = count.get(c["model"], 0) + n
    assert count["iscwsa:SPE90408_Ex1"] == 66 and count["iscwsa:SPE90408_Ex6"] == 90
    assert sum(count[f"iscwsa:SPE90408_Ex{i}"] for i in (2, 3, 4, 5)) == 336
    assert ae.inputs["azimuth"] == "utm_grid"
    assert ae.inputs["wells"] == {"1": {"lon": 2.0, "zone": 31}, "2": {"lon": -90.0, "zone": 15},
                                  "3": {"lon": 147.0, "zone": 55}}


def test_vector_models_exist():
    used = set()
    for vs in (read_vectors(T3), read_vectors(AE)):
        for c in vs.cases:
            used |= {c["model"]} if "model" in c else {leg["model"] for leg in c["legs"]}
    assert len(used) == 8
    for m in used:
        ns, name = m.split(":")
        assert any((ROOT / d / ns / f"{name}.json").is_file() for d in ("models", "conformance/models")), m


def test_spot_values():
    t3 = read_vectors(T3)
    assert t3.cases[0]["results"][0]["sigma_hla"] == [20.116, 84.342, 8.626]
    assert t3.source["table"] == "Table 3"
    ae = read_vectors(AE)
    case = next(c for c in ae.cases if c["model"] == "iscwsa:SPE90408_Ex4" and c["well"] == 3)
    assert next(r for r in case["results"] if r["md"] == 4030)["nev"] == [1408, 1094, -27, 1423, -1, 44]
    assert ae.known_misses == [{"model": "iscwsa:SPE90408_Ex1", "well": 3, "md": 3000, "element": "NN",
                                "reason": ae.known_misses[0]["reason"]}]


def test_tolerance_rules():
    hla = tolerance("hla")
    assert hla(20.2, 20.116) and not hla(20.25, 20.116)
    assert hla(0.001, 0.0) and not hla(0.003, 0.0)
    assert hla(0.51, 0.5, correlation=True) and not hla(0.52, 0.5, correlation=True)
    nev = tolerance("total_nev")
    assert nev(201, 199) and not nev(202.5, 200)
    assert nev(1000, 995) and not nev(1011, 1000)
    with pytest.raises(ValueError):
        tolerance("per_term_nev")
