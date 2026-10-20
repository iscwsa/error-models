# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Content hashing and UUIDv5 identity for model and library documents."""
import copy
import hashlib
import uuid
from typing import Mapping

import rfc8785

NAMESPACE_UUID = uuid.UUID("7c9fcf73-f032-422d-b9aa-a2d69fa46e1d")
_EXCLUDED = ("hash_value", "$schema")


def _digest(doc: Mapping) -> str:
    body = {k: v for k, v in doc.items() if k not in _EXCLUDED}
    return hashlib.sha256(rfc8785.dumps(body)).hexdigest()


def content_hash(doc: Mapping) -> str:
    return _digest(doc)


def entry_hash(entry: Mapping) -> str:
    return _digest(entry)


def model_uuid(namespace: str, model_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE_UUID, f"{namespace}:{model_id}"))


ENTRY_SECTIONS = ("weighting_function", "term")


def entry_uuid(library_id: str, section: str, name: str) -> str:
    """UUIDv5 of a library entry; the section keeps a weighting function and a term of the same key distinct."""
    if section not in ENTRY_SECTIONS:
        raise ValueError(f"section must be one of {ENTRY_SECTIONS}, got {section!r}")
    return str(uuid.uuid5(NAMESPACE_UUID, f"{library_id}/{section}/{name}"))


def library_uuid(library_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE_UUID, library_id))


def stamp(doc: dict) -> dict:
    """Return a deep copy with entry hashes (libraries) and hash_value filled."""
    out = copy.deepcopy(doc)
    for section in ("weighting_functions", "terms"):
        entries = out.get(section)
        if isinstance(entries, Mapping):  # models carry terms as a list
            for entry in entries.values():
                entry["hash_value"] = entry_hash(entry)
    out["hash_value"] = content_hash(out)
    return out
