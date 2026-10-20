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
