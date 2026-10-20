# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Repository validator: schemas, hashes, UUIDs, cross references and formulas.

Never touches the network and never evaluates formulas (see tools/formula.py).
Usage: python -m tools.validate [--registry] [--release] [ROOT]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tools.formula import VARIABLES, FormulaError, parse
from tools.identity import content_hash, entry_hash, entry_uuid, library_uuid, model_uuid

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SCHEMA_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/iscwsa/error-models/([^/]+)/schemas/(model|library)\.json$"
)
FORMULA_FIELDS = (
    "depth", "inclination", "azimuth",
    "singularity_north", "singularity_east", "singularity_vertical",
)


@dataclass
class Problem:
    code: str
    file: str
    detail: str


class _DuplicateKey(Exception):
    pass


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen[key] = value
    return seen


def _schema_dir(root: Path, release: str) -> Path | None:
    """Local schema directory for a release; None if none is bundled.

    A root without its own schemas (e.g. a test repo) falls back to this checkout's.
    """
    candidates = (
        [root / "schemas", PACKAGE_ROOT / "schemas"]
        if release == "main"
        else [root / "tools" / "schemas" / release, PACKAGE_ROOT / "tools" / "schemas" / release]
    )
    return next((d for d in candidates if d.is_dir()), None)


class _Schemas:
    """Per-release validators, built from local schema files only."""

    def __init__(self, root: Path):
        self.root = root
        self._cache: dict[str, dict[str, Draft202012Validator]] = {}

    def get(self, release: str, kind: str) -> Draft202012Validator:
        if release not in self._cache:
            self._cache[release] = self._build(release)
        return self._cache[release][kind]

    def _build(self, release: str) -> dict[str, Draft202012Validator]:
        directory = _schema_dir(self.root, release)
        registry = Registry()
        for path in sorted(directory.rglob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            registry = registry.with_resource(
                schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
            )
        out = {}
        for kind in ("model", "library"):
            schema = json.loads((directory / f"{kind}.json").read_text(encoding="utf-8"))
            out[kind] = Draft202012Validator(
                schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
            )
        return out


def _release_of(doc) -> str | None:
    url = doc.get("$schema") if isinstance(doc, dict) else None
    m = SCHEMA_URL_RE.match(url) if isinstance(url, str) else None
    return m.group(1) if m else None


def _path(error) -> str:
    return "/".join(str(p) for p in error.absolute_path) or "(root)"


def _namespace_part(qualified) -> str | None:
    return qualified.split(":", 1)[0] if isinstance(qualified, str) and ":" in qualified else None


def _qualified_id(kind: str, doc: dict):
    if kind == "library":
        return doc.get("library_id")
    meta = doc.get("metadata")
    return meta.get("model_id") if isinstance(meta, dict) else None


def _load(path: Path, rel: str, problems: list[Problem]):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
    except _DuplicateKey as exc:
        problems.append(Problem("DUPLICATE_TERM", rel, f"duplicate key {exc.args[0]!r}"))
    except (ValueError, OSError) as exc:
        problems.append(Problem("SCHEMA", rel, f"cannot parse JSON: {exc}"))
    return None


def _check_formula(text, rel, where, problems):
    try:
        parse(text, allowed=VARIABLES)
    except FormulaError as exc:
        problems.append(Problem("FORMULA", rel, f"{where}: {exc}"))


def _check_library(doc, rel, problems):
    lib_id = doc["library_id"]
    if doc["uuid"] != library_uuid(lib_id):
        problems.append(Problem("UUID", rel, f"library uuid should be {library_uuid(lib_id)}"))
    wfs, terms = doc["weighting_functions"], doc["terms"]
    for section, entries in (("weighting_functions", wfs), ("terms", terms)):
        for key, entry in entries.items():
            where = f"{section}/{key}"
            if entry["uuid"] != entry_uuid(lib_id, key):
                problems.append(Problem("UUID", rel, f"{where}: uuid should be {entry_uuid(lib_id, key)}"))
            if entry["hash_value"] != entry_hash(entry):
                problems.append(Problem("ENTRY_HASH", rel, f"{where}: hash_value does not match content"))
            for erratum in entry.get("errata", []):
                if erratum["status"] == "proposed":
                    problems.append(Problem("ERRATA_PROPOSED", rel, f"{where}: erratum on {erratum['field']!r} is proposed"))
                if section == "weighting_functions" and erratum["field"] in FORMULA_FIELDS:
                    _check_formula(erratum["corrected"], rel, f"{where}/errata[{erratum['field']}]", problems)
    for key, wf in wfs.items():
        for field in FORMULA_FIELDS:
            if field in wf:
                _check_formula(wf[field], rel, f"weighting_functions/{key}/{field}", problems)
    for key, term in terms.items():
        if term["weighting_function"] not in wfs:
            problems.append(Problem("WF_MISSING", rel, f"terms/{key}: weighting function {term['weighting_function']!r} not in library"))
    if doc["hash_value"] != content_hash(doc):
        problems.append(Problem("HASH", rel, "hash_value does not match content"))


def _check_model(doc, rel, libraries, releases, own_release, problems):
    model_id = doc["metadata"]["model_id"]
    ns, _, name = model_id.partition(":")
    if doc["metadata"]["model_uuid"] != model_uuid(ns, name):
        problems.append(Problem("UUID", rel, f"model_uuid should be {model_uuid(ns, name)}"))
    if doc["hash_value"] != content_hash(doc):
        problems.append(Problem("HASH", rel, "hash_value does not match content"))
    referenced = []
    all_found = True
    for ref in doc["libraries"]:
        lib = libraries.get(ref["id"])
        if lib is None:
            problems.append(Problem("LIBRARY_MISSING", rel, f"no library file with library_id {ref['id']!r}"))
            all_found = False
            continue
        referenced.append(lib)
        if ref["uuid"] != lib["uuid"] or ref["hash_value"] != lib["hash_value"]:
            problems.append(Problem("LIBRARY_HASH", rel, f"pinned uuid/hash for {ref['id']!r} differ from the library file"))
        lib_release = releases[ref["id"]]
        if lib_release != own_release:
            problems.append(Problem("RELEASE_MISMATCH", rel, f"model is release {own_release!r} but library {ref['id']!r} is {lib_release!r}"))
    seen = set()
    for term in doc["terms"]:
        tname = term["term"]
        if tname in seen:
            problems.append(Problem("DUPLICATE_TERM", rel, f"term {tname!r} listed more than once"))
        seen.add(tname)
        tns, _, key = tname.rpartition(":")
        tns = tns or "iscwsa"
        found = any(
            lib["library_id"].split(":", 1)[0] == tns and key in lib["terms"] for lib in referenced
        )
        if not found and all_found:  # a missing library would cascade into every term
            problems.append(Problem("TERM_MISSING", rel, f"term {tname!r} not found in the referenced libraries"))


def validate_repo(root: Path, registry_check: bool = False) -> list[Problem]:
    root = Path(root)
    problems: list[Problem] = []
    schemas = _Schemas(root)
    namespaces: set[str] = set()
    if registry_check:
        try:
            registry = json.loads((root / "namespaces.json").read_text(encoding="utf-8"))
            namespaces = {k for k in registry if k != "$comment"}
        except (OSError, ValueError) as exc:
            problems.append(Problem("SCHEMA", "namespaces.json", f"cannot read namespace registry: {exc}"))

    files = []  # (kind, rel, doc, release)
    for kind, folder in (("library", "library"), ("model", "models")):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            rel = path.relative_to(root).as_posix()
            doc = _load(path, rel, problems)
            if doc is None:
                continue
            release = _release_of(doc)
            if release is None:
                shown = doc.get("$schema") if isinstance(doc, dict) else doc
                problems.append(Problem("UNKNOWN_RELEASE", rel, f"unrecognised $schema {shown!r}"))
            elif _schema_dir(root, release) is None:
                problems.append(Problem("UNKNOWN_RELEASE", rel, f"no bundled schemas for release {release!r}"))
            else:
                files.append((kind, rel, doc, release))

    libraries: dict[str, dict] = {}
    releases: dict[str, str] = {}
    models = []
    for kind, rel, doc, release in files:
        qualified = _qualified_id(kind, doc)
        ns = _namespace_part(qualified)
        ns_bad = ns is not None and not NAMESPACE_RE.match(ns)
        if ns_bad:
            problems.append(Problem("NAMESPACE_SYNTAX", rel, f"namespace {ns!r} of {qualified!r} is invalid"))
        elif registry_check and ns is not None and ns not in namespaces:
            problems.append(Problem("NAMESPACE_UNREGISTERED", rel, f"namespace {ns!r} is not in namespaces.json"))
        errors = list(schemas.get(release, kind).iter_errors(doc))
        if ns_bad:  # already reported; drop the schema's complaint about the same id
            errors = [e for e in errors if _path(e) not in ("library_id", "metadata/model_id")]
        for err in errors:
            problems.append(Problem("SCHEMA", rel, f"{_path(err)}: {err.message}"))
        if errors or ns_bad:
            continue
        if kind == "library":
            _check_library(doc, rel, problems)
            libraries[doc["library_id"]] = doc
            releases[doc["library_id"]] = release
        else:
            models.append((rel, doc, release))

    for rel, doc, release in models:
        _check_model(doc, rel, libraries, releases, release, problems)
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.validate")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--registry", action="store_true", help="also require namespaces to be in namespaces.json")
    parser.add_argument("--release", action="store_true", help="treat proposed errata as errors")
    args = parser.parse_args(argv)
    problems = validate_repo(Path(args.root), registry_check=args.registry)
    failed = 0
    for p in problems:
        warning = p.code == "ERRATA_PROPOSED" and not args.release
        print(f"{'warning: ' if warning else ''}{p.file}: {p.code}: {p.detail}")
        failed += not warning
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
