# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Tests for the model and library JSON schemas."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _registry():
    registry = Registry()
    for path in sorted((ROOT / "schemas").rglob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
        )
    return registry


REGISTRY = _registry()
BASE = "https://raw.githubusercontent.com/iscwsa/error-models/main/schemas/"


def errors(name, instance):
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema, registry=REGISTRY, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    return list(validator.iter_errors(instance))


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_minimal_model_valid():
    assert errors("model.json", load("minimal_model.json")) == []


def test_minimal_library_valid():
    assert errors("library.json", load("minimal_library.json")) == []


def test_wrong_schema_url_rejected():
    model = load("minimal_model.json")
    model["$schema"] = "https://raw.githubusercontent.com/iscwsa/error-models/v9.9/schemas/model.json"
    errs = errors("model.json", model)
    assert any(e.validator == "const" for e in errs)


def test_unknown_property_rejected():
    model = load("minimal_model.json")
    model["extra"] = 1
    assert errors("model.json", model)


def test_revision_must_be_string():
    model = load("minimal_model.json")
    model["metadata"]["revision"] = 5.1
    assert errors("model.json", model)


def test_negative_magnitude_rejected():
    model = load("minimal_model.json")
    model["terms"][0]["magnitude"] = -0.1
    assert errors("model.json", model)


def test_namespace_pattern():
    lib = load("minimal_library.json")
    lib["library_id"] = "BH:x"
    assert errors("library.json", lib)
    lib["library_id"] = "bh:x"
    assert errors("library.json", lib) == []


def test_every_schema_id_is_base_plus_path():
    for path in (ROOT / "schemas").rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$id"] == BASE + path.relative_to(ROOT / "schemas").as_posix()


def test_errata_allowed_on_term_and_weighting_function():
    lib = load("minimal_library.json")
    erratum = {"field": "units", "sheet_text": "deg", "corrected": "rad", "source": "x", "reason": "y", "status": "proposed"}
    lib = copy.deepcopy(lib)
    next(iter(lib["terms"].values()))["errata"] = [erratum]
    next(iter(lib["weighting_functions"].values()))["errata"] = [erratum]
    assert errors("library.json", lib) == []
    erratum["status"] = "bogus"
    assert errors("library.json", lib)


def test_namespaces_json_entries():
    ns = json.loads((ROOT / "namespaces.json").read_text(encoding="utf-8"))
    ns.pop("$comment", None)
    assert set(ns) == {"iscwsa", "generic_iscwsa", "owsg"}
    for key, entry in ns.items():
        assert errors("namespace.json", key) == []
        assert set(entry) == {"organisation", "contact", "added", "description"}


def test_metadata_replaces_text_allowed():
    model = load("minimal_model.json")
    model["metadata"]["replaces_text"] = "Replaces Rev4"
    assert errors("model.json", model) == []
    model["metadata"]["replaces_text"] = ""
    assert errors("model.json", model)


def test_library_with_term_groups_valid():
    lib = load("minimal_library.json")
    assert lib["term_groups"]
    assert errors("library.json", lib) == []
    lib["term_groups"][0]["terms"] = ["iscwsa:PA", "PB"]
    assert errors("library.json", lib) == []


def test_group_needs_two_terms():
    lib = load("minimal_library.json")
    lib["term_groups"][0]["terms"] = ["PA"]
    assert errors("library.json", lib)
    lib["term_groups"][0]["terms"] = ["PA", "PA"]
    assert errors("library.json", lib)


def test_group_needs_source():
    lib = load("minimal_library.json")
    lib["term_groups"][0]["source"] = ""
    assert errors("library.json", lib)


def test_term_requires_optional_string_array():
    lib = load("minimal_library.json")
    lib["terms"]["DREF"]["requires"] = ["gyro_modes"]
    assert errors("library.json", lib) == []
    lib["terms"]["DREF"]["requires"] = [""]
    assert errors("library.json", lib)


def _pv(n, unit="deg"):
    return {"value": n, "unit": unit, "text": f"{n} {unit}"}


GYRO = {
    "accelerometer": "xyz",
    "external_reference": False,
    "stationary": {"axes": "xy", "start_inc": _pv(0), "end_inc": _pv(15), "init_inc": _pv(15)},
    "continuous": [
        {"axes": "xy", "start_inc": _pv(15), "end_inc": _pv(150), "init_inc": _pv(15), "gyro_speed": _pv(2743.2, "m/hr")}
    ],
    "min_distance": _pv(99999, "m"),
    "init_factor": {"value": 0.4082, "unit": "-", "text": "0.4082"},
}


def test_gyro_block_validates():
    assert errors("gyro.json", GYRO) == []
    assert errors("gyro.json", {"continuous": []}) == []


def test_gyro_block_rejects_bad_input():
    bad_axes = copy.deepcopy(GYRO)
    bad_axes["continuous"][0]["axes"] = "x"
    assert errors("gyro.json", bad_axes)
    no_speed = copy.deepcopy(GYRO)
    del no_speed["continuous"][0]["gyro_speed"]
    assert errors("gyro.json", no_speed)
    extra = copy.deepcopy(GYRO)
    extra["stationary"]["gyro_speed"] = _pv(1, "m/hr")
    assert errors("gyro.json", extra)


def test_model_accepts_optional_gyro():
    model = load("minimal_model.json")
    model["gyro"] = GYRO
    assert errors("model.json", model) == []
    model["gyro"] = {"stationary": GYRO["stationary"]}
    assert errors("model.json", model)
