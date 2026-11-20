# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import pytest

from tools.identity import (content_hash, entry_hash, model_uuid, entry_uuid,
                            library_uuid, stamp)


def test_hash_known_vector():
    assert content_hash({"b": 1, "a": "x"}) == "cdab067e9f3beb32d1252cfd63e492592fecbf591b0d08cadb24bb17f3864246"


def test_hash_ignores_schema_and_hash_value():
    d = {"$schema": "u1", "a": 1, "hash_value": "zz"}
    assert content_hash(d) == content_hash({"$schema": "u2", "a": 1})


def test_hash_detects_magnitude_edit():
    assert content_hash({"terms": [{"term": "DRFR", "magnitude": 0.35}]}) != content_hash({"terms": [{"term": "DRFR", "magnitude": 0.36}]})


def test_uuids_deterministic():
    assert model_uuid("iscwsa", "A001Mc") == model_uuid("iscwsa", "A001Mc") != model_uuid("generic_iscwsa", "A001Mc")
    assert entry_uuid("lib", "term", "x") != entry_uuid("lib", "term", "y")
    assert library_uuid("lib") == library_uuid("lib")


def test_entry_hash_ignores_hash_value():
    assert entry_hash({"a": 1, "hash_value": "q"}) == entry_hash({"a": 1})


def test_stamp_library_and_no_mutation():
    lib = {"$schema": "s", "terms": {"T": {"a": 1}}, "weighting_functions": {"W": {"b": 2}}}
    out = stamp(lib)
    assert "hash_value" not in lib and "hash_value" not in lib["terms"]["T"]
    assert out["terms"]["T"]["hash_value"] == entry_hash({"a": 1})
    assert out["weighting_functions"]["W"]["hash_value"] == entry_hash({"b": 2})
    assert out["hash_value"] == content_hash(out)


def test_stamp_model():
    out = stamp({"a": 1})
    assert out["hash_value"] == content_hash({"a": 1})


def test_stamp_model_with_list_terms():
    model = {"terms": [{"term": "DRFR", "magnitude": 0.35}]}
    out = stamp(model)
    assert out["terms"] == [{"term": "DRFR", "magnitude": 0.35}]
    assert out["hash_value"] == content_hash(model)
    assert "hash_value" not in out["terms"][0]


def test_uuid_known_vectors():
    assert model_uuid("iscwsa", "A001Mc") == "e02849fe-b12c-570d-ab65-fb8463ab7b43"
    assert entry_uuid("iscwsa:rev5", "weighting_function", "DBH") == "4223ca47-c982-58cc-b112-d5ba3660cca9"
    assert entry_uuid("iscwsa:rev5", "term", "DBH") == "af792c31-3330-5ef7-85e4-4f09425136f6"
    assert library_uuid("iscwsa:rev5") == "afcf8ed3-ac41-51f8-9999-8d126737f2f0"


def test_entry_uuid_differs_between_sections():
    assert entry_uuid("lib", "weighting_function", "K") != entry_uuid("lib", "term", "K")


def test_entry_uuid_rejects_unknown_section():
    with pytest.raises(ValueError):
        entry_uuid("lib", "terms", "K")
