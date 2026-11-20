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

from tools.formula import VARIABLES, FormulaError, continuous_kind, parse
from tools.identity import content_hash, entry_hash, entry_uuid, library_uuid, model_uuid

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TERM_GYRO = json.loads((Path(__file__).resolve().parent / "term_gyro.json").read_text(encoding="utf-8"))
NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SCHEMA_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/iscwsa/error-models/([^/]+)/schemas/(model|library)\.json$"
)
TAG_RE = re.compile(r"^(?:main|v?\d[\w.\-]*)$")
FORMULA_FIELDS = (
    "depth", "inclination", "azimuth",
    "singularity_north", "singularity_east", "singularity_vertical",
)


@dataclass
class Problem:
    code: str
    file: str
    detail: str


def _loads_tracking_duplicates(text: str):
    """Parse JSON, returning (doc, [(mapping, key), ...]) for every repeated key."""
    dups = []

    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                dups.append((out, key))
            out[key] = value
        return out

    return json.loads(text, object_pairs_hook=hook), dups


def _schema_dir(root: Path, release: str) -> Path | None:
    """Local schema directory for a release; None if none is bundled.

    A root without its own schemas (e.g. a test repo) falls back to this checkout's.
    """
    # The PACKAGE_ROOT fallback only exists so test repos built in tmp dirs can validate
    # without copying the schemas; a real checkout always has its own schemas/.
    candidates = (
        [root / "schemas", PACKAGE_ROOT / "schemas"]
        if release == "main"
        else [root / "tools" / "schemas" / release, PACKAGE_ROOT / "tools" / "schemas" / release]
    )
    return next((d for d in candidates if (d / "model.json").is_file() and (d / "library.json").is_file()), None)


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
    return m.group(1) if m and TAG_RE.match(m.group(1)) and ".." not in m.group(1) else None


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
        doc, dups = _loads_tracking_duplicates(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        problems.append(Problem("SCHEMA", rel, f"cannot parse JSON: {exc}"))
        return None
    if dups:
        entry_maps = [doc.get(k) for k in ("terms", "weighting_functions")] if isinstance(doc, dict) else []
        for mapping, key in dups:
            code = "DUPLICATE_TERM" if any(mapping is m for m in entry_maps) else "DUPLICATE_KEY"
            problems.append(Problem(code, rel, f"duplicate key {key!r}"))
        return None
    return doc


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
    for section, kind, entries in (("weighting_functions", "weighting_function", wfs), ("terms", "term", terms)):
        for key, entry in entries.items():
            where = f"{section}/{key}"
            if entry["uuid"] != entry_uuid(lib_id, kind, key):
                problems.append(Problem("UUID", rel, f"{where}: uuid should be {entry_uuid(lib_id, kind, key)}"))
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
            continue
        source = wfs[term["weighting_function"]].get("source", "")
        want = TERM_GYRO.get(source, {})
        if (term.get("mode"), term.get("init")) != (want.get("mode"), want.get("init")):
            problems.append(Problem(
                "GYRO_SOURCE", rel,
                f"terms/{key}: mode {term.get('mode')!r}, init {term.get('init')!r} disagree with its source {source!r}"))
    union = {cap for term in terms.values() for cap in term.get("requires", [])}
    if set(doc["requires"]) != union:
        problems.append(Problem("REQUIRES_MISMATCH", rel, f"requires {sorted(doc['requires'])} but terms need {sorted(union)}"))
    for n, group in enumerate(doc.get("term_groups", [])):
        for member in group["terms"]:
            if _member_key(member, lib_id) not in terms:
                problems.append(Problem("GROUP_UNKNOWN_TERM", rel, f"term_groups[{n}]: {member!r} is not a term of this library"))
    if doc["hash_value"] != content_hash(doc):
        problems.append(Problem("HASH", rel, "hash_value does not match content"))


def _split_name(name: str, default_ns: str = "iscwsa") -> tuple[str, str]:
    ns, _, key = name.rpartition(":")
    return (ns or default_ns, key)


def _member_key(member: str, lib_id: str):
    """Key of a group member inside its own library, or None if it names another namespace."""
    ns, key = _split_name(member, lib_id.split(":", 1)[0])
    return key if ns == lib_id.split(":", 1)[0] else None


def _check_groups(rel, model_terms, referenced, problems):
    """model_terms: {(namespace, key): magnitude}."""
    for lib in referenced:
        lib_ns = lib["library_id"].split(":", 1)[0]
        for n, group in enumerate(lib.get("term_groups", [])):
            keys = [_member_key(m, lib["library_id"]) for m in group["terms"]]
            members = [k for k in keys if k is not None and k in lib["terms"]]
            used = [k for k in members if (lib_ns, k) in model_terms]
            where = f"{lib['library_id']} term_groups[{n}]"
            if not used:
                continue
            if len(used) < len(members):
                missing = sorted(set(members) - set(used))
                problems.append(Problem("INCOMPLETE_GROUP", rel, f"{where}: uses {sorted(used)} but not {missing}"))
                continue
            if len({model_terms[(lib_ns, k)] for k in used}) > 1:
                problems.append(Problem("GROUP_MISMATCH", rel, f"{where}: members have different magnitudes"))
            elif len({lib["terms"][k]["propagation"] for k in used}) > 1:
                problems.append(Problem("GROUP_MISMATCH", rel, f"{where}: members have different propagations"))


def _check_gyro(doc, rel, referenced, problems):
    """The model's gyro block against the mode terms it uses: ranges, init, and the axes each continuous term needs."""
    mode_terms = []  # (name, library term, weighting function)
    for term in doc["terms"]:
        tns, key = _split_name(term["term"])
        for lib in referenced:
            entry = lib["terms"].get(key) if lib["library_id"].split(":", 1)[0] == tns else None
            if entry is not None and "mode" in entry:
                mode_terms.append((term["term"], entry, lib["weighting_functions"].get(entry["weighting_function"])))
    gyro = doc.get("gyro")
    if gyro is None:
        if mode_terms:
            problems.append(Problem("GYRO_BLOCK_MISSING", rel, f"{mode_terms[0][0]!r} has a survey mode but the model has no gyro block"))
        return
    stationary = [("stationary", gyro["stationary"])] if "stationary" in gyro else []
    blocks = stationary + [(f"continuous {b['axes']}", b) for b in gyro.get("continuous", [])]
    ranges = []
    for label, b in blocks:
        start, end = b["start_inc"]["value"], b["end_inc"]["value"]
        if start >= end:
            problems.append(Problem("GYRO_RANGE", rel, f"gyro {label}: start inclination {start} is not below end {end}"))
        else:
            ranges.append((label, start, end))
    for i, (la, sa, ea) in enumerate(ranges):
        for lb, sb, eb in ranges[i + 1:]:
            if sa < eb and sb < ea:
                problems.append(Problem("GYRO_RANGE", rel, f"gyro {la} ({sa}-{ea}) overlaps {lb} ({sb}-{eb})"))
    continuous = gyro.get("continuous", [])
    if len({b["init_inc"]["value"] for b in continuous}) > 1:
        problems.append(Problem("GYRO_INIT_MISMATCH", rel, "continuous gyro blocks have different init_inc"))
    axes_list = [b["axes"] for b in continuous]
    if len(set(axes_list)) < len(axes_list):
        problems.append(Problem("GYRO_AXES_DUPLICATE", rel, f"two continuous gyro blocks have the same axes: {sorted(axes_list)}"))
    if continuous and "min_distance" not in gyro:
        problems.append(Problem("GYRO_MIN_DISTANCE_MISSING", rel, "the gyro block has a continuous block but no min_distance"))
    have = set(axes_list)
    for name, entry, wf in mode_terms:
        if entry["mode"] != "continuous" or wf is None:
            continue
        try:
            axes, _ = continuous_kind(wf["azimuth"])
        except FormulaError as exc:
            problems.append(Problem("FORMULA", rel, f"{name}: {exc}"))
            continue
        if axes not in have:
            problems.append(Problem("GYRO_AXES_MISSING", rel, f"{name} needs a continuous {axes} block; the model has {sorted(have) or 'none'}"))


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
        tns, key = _split_name(tname)
        defining = [
            lib["library_id"] for lib in referenced if lib["library_id"].split(":", 1)[0] == tns and key in lib["terms"]
        ]
        found = bool(defining)
        if len(defining) > 1:
            problems.append(Problem("AMBIGUOUS_TERM", rel, f"term {tname!r} is defined by more than one library: {defining}"))
        if not found and all_found:  # a missing library would cascade into every term
            problems.append(Problem("TERM_MISSING", rel, f"term {tname!r} not found in the referenced libraries"))
    model_terms = {}
    for term in doc["terms"]:
        model_terms.setdefault(_split_name(term["term"]), term["magnitude"])
    _check_groups(rel, model_terms, referenced, problems)
    _check_gyro(doc, rel, referenced, problems)


def validate_repo(root: Path, registry_check: bool = False) -> list[Problem]:
    root = Path(root)
    problems: list[Problem] = []
    schemas = _Schemas(root)
    namespaces: set[str] = set()
    if registry_check:  # on failure, report once and skip the per-file namespace checks
        try:
            registry = json.loads((root / "namespaces.json").read_text(encoding="utf-8"))
            namespaces = {k for k in registry if k != "$comment"}
        except (OSError, ValueError) as exc:
            problems.append(Problem("SCHEMA", "namespaces.json", f"cannot read namespace registry: {exc}"))
            registry_check = False

    files = []  # (kind, rel, doc, release)
    for kind, folder in (("library", "library"), ("model", "models"), ("model", "conformance/models")):
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
            if doc["library_id"] in libraries:
                problems.append(Problem("DUPLICATE_LIBRARY", rel, f"library_id {doc['library_id']!r} already defined by another file"))
                continue
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
