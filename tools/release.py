# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Release tooling (docs/releasing.md).

  python -m tools.release cut vX.Y.Z [--workbooks DIR | --no-workbooks]   point every file at the tag, copy the schemas
                                                                          into tools/schemas/<tag>/, close the changelog
  python -m tools.release reopen                                          point every file back at main
  python -m tools.release check [--tag vX.Y.Z]                            the tree is at one release (and the tag's)

A cut changes only URLs: the hash excludes $schema, so no hash_value changes, and a cut that would change one stops
(HASH_CHANGED). Every write goes through one staged step that puts the tree back as it was if any write fails.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from tools.identity import content_hash
from tools.urls import BASE, tree_release

ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
# Every JSON file that carries schema URLs; tools/schemas/<release>/ holds the released copies and is never rewritten
TREE_DIRS = ("schemas", "library", "models", "conformance", "tests/fixtures")
HASHED_DIRS = ("library", "models", "conformance/models")
URL_KEYS = ("$schema", "$id", "const")
_URL_RE = re.compile(re.escape(BASE) + r'([^/"\s]+)/schemas/')
CHANGELOG = "CHANGELOG.md"
UNRELEASED = "## Unreleased"


class ReleaseError(ValueError):
    """codes: BAD_VERSION, NOT_MAIN, DIRTY, NOT_VALID, EMPTY_UNRELEASED, NOT_NEWER, EXISTS, NO_WORKBOOKS,
    NOT_DETERMINISTIC, HASH_CHANGED."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass
class CutReport:
    version: str
    files_rewritten: int
    schemas_copied: int
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def _version(v: str) -> tuple[int, int, int]:
    m = VERSION_RE.match(v)
    if m is None:
        raise ReleaseError("BAD_VERSION", f"{v!r} is not vMAJOR.MINOR.PATCH")
    return tuple(int(x) for x in m.groups())


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True,
                          encoding="utf-8").stdout


def _tags(root: Path) -> list[str]:
    """The repository's vX.Y.Z tags, oldest version first."""
    return sorted((t for t in _git(root, "tag", "--list", "v*").split() if VERSION_RE.match(t)), key=_version)


def _files(root: Path) -> list[Path]:
    return sorted(p for d in TREE_DIRS if (root / d).is_dir() for p in (root / d).rglob("*.json"))


def rewrite_text(text: str, old: str, new: str) -> str:
    return text.replace(f"{BASE}{old}/", f"{BASE}{new}/")


def rewrite_urls(doc, release: str, old: str = "main"):
    """A copy of doc with every `<BASE><old>/` in a $schema, $id or const value changed to `<BASE><release>/`."""
    if isinstance(doc, dict):
        return {k: (rewrite_text(v, old, release) if k in URL_KEYS and isinstance(v, str) else rewrite_urls(v, release, old))
                for k, v in doc.items()}
    if isinstance(doc, list):
        return [rewrite_urls(v, release, old) for v in doc]
    return doc


def _rewrite_all(root: Path, old: str, new: str) -> dict[Path, str]:
    """{path: new text} for every tree file that names release `old`; only the URL keys may change."""
    out = {}
    for p in _files(root):
        text = p.read_text(encoding="utf-8")
        new_text = rewrite_text(text, old, new)
        if new_text == text:
            continue
        if json.loads(new_text) != rewrite_urls(json.loads(text), new, old):
            raise ReleaseError("HASH_CHANGED", f"{p.relative_to(root).as_posix()}: a URL outside $schema / $id / const")
        out[p] = new_text
    return out


def _check_hashes(root: Path, texts: dict[Path, str]) -> None:
    """Every model and library, as it will be written, has a hash_value equal to its content's (HASH_CHANGED)."""
    for p in _files(root):
        rel = p.relative_to(root).as_posix()
        if not rel.startswith(tuple(d + "/" for d in HASHED_DIRS)):
            continue
        doc = json.loads(texts.get(p) or p.read_text(encoding="utf-8"))
        if doc.get("hash_value") != content_hash(doc):
            raise ReleaseError("HASH_CHANGED", f"{rel}: hash_value does not match the content")


def _unreleased(text: str) -> tuple[int, int]:
    """(start of the '## Unreleased' heading, end of its section) in the changelog."""
    start = text.find(f"\n{UNRELEASED}\n")
    if start < 0:
        raise ReleaseError("EMPTY_UNRELEASED", f"{CHANGELOG} has no '{UNRELEASED}' section")
    start += 1
    nxt = text.find("\n## ", start + len(UNRELEASED))
    return start, (nxt + 1 if nxt >= 0 else len(text))


def _ids(docs: dict[str, dict]) -> dict[str, str]:
    """{qualified id: hash_value} of models and libraries."""
    out = {}
    for doc in docs.values():
        qid = doc.get("library_id") or doc.get("metadata", {}).get("model_id")
        if qid:
            out[qid] = doc["hash_value"]
    return out


def _current_docs(root: Path) -> dict[str, dict]:
    return {p.relative_to(root).as_posix(): json.loads(p.read_text(encoding="utf-8"))
            for d in HASHED_DIRS if (root / d).is_dir() for p in (root / d).rglob("*.json")}


def _tag_docs(root: Path, tag: str) -> dict[str, dict]:
    paths = [p for p in _git(root, "ls-tree", "-r", "--name-only", tag).splitlines()
             if p.endswith(".json") and p.startswith(tuple(d + "/" for d in HASHED_DIRS))]
    return {p: json.loads(_git(root, "show", f"{tag}:{p}")) for p in paths}


def change_list(root: Path, previous: str | None) -> tuple[list[str], list[str], list[str]]:
    """(added, changed, removed) qualified ids against the previous tag, by hash_value; all added for the first."""
    now = _ids(_current_docs(root))
    before = _ids(_tag_docs(root, previous)) if previous else {}
    added = sorted(set(now) - set(before))
    changed = sorted(k for k in set(now) & set(before) if now[k] != before[k])
    removed = sorted(set(before) - set(now))
    return added, changed, removed


def _section(title: str, ids: list[str]) -> str:
    return f"### {title}\n\n" + "".join(f"- `{i}`\n" for i in ids) + "\n" if ids else ""


def determinism(root: Path, workbooks: Path | None) -> list[str]:
    """The generated files that differ from the committed ones: tools.make_spe90408, and tools.extract_xlsx when the
    workbooks are given."""
    from tools import make_spe90408
    differ = make_spe90408.check(root)
    if workbooks is not None:
        from tools import extract_xlsx
        differ += extract_xlsx.check(workbooks, root)
    return differ


def apply(writes: dict[Path, str]) -> None:
    """Write every file, or none: on any failure the files already replaced get their old bytes back, new files and
    directories are removed, and the error is raised again."""
    before = {p: (p.read_bytes() if p.exists() else None) for p in writes}
    new_dirs = []
    for p in writes:
        for d in reversed(p.parents):
            if not d.exists() and d not in new_dirs:
                new_dirs.append(d)
    staged = {}
    try:
        for d in new_dirs:
            d.mkdir()
        for p, text in writes.items():
            tmp = p.with_name(p.name + ".release-tmp")
            tmp.write_bytes(text.encode("utf-8"))
            staged[p] = tmp
        for p, tmp in staged.items():
            os.replace(tmp, p)
    except BaseException:
        for p, old in before.items():
            if old is None:
                if p.exists():
                    p.unlink()
            elif not p.exists() or p.read_bytes() != old:
                p.write_bytes(old)
        for tmp in staged.values():
            if tmp.exists():
                tmp.unlink()
        for d in reversed(new_dirs):
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
        raise


def cut(root: Path, version: str, today: date, workbooks: Path | None = None,
        allow_no_workbooks: bool = False) -> CutReport:
    from tools.validate import validate_repo
    root = Path(root)
    _version(version)
    if tree_release(root) != "main":
        raise ReleaseError("NOT_MAIN", f"the tree is at release {tree_release(root)}; run reopen first")
    if _git(root, "status", "--porcelain").strip():
        raise ReleaseError("DIRTY", "the working tree has uncommitted changes")
    tags = _tags(root)
    if version in tags or (root / "tools" / "schemas" / version).exists():
        raise ReleaseError("EXISTS", f"{version} is already a tag or has tools/schemas/{version}/")
    if tags and _version(version) <= _version(tags[-1]):
        raise ReleaseError("NOT_NEWER", f"{version} is not after the last release {tags[-1]}")
    _check_hashes(root, {})
    problems = validate_repo(root, registry_check=True)
    if problems:
        shown = "; ".join(f"{p.file}: {p.code}" for p in problems[:5])
        raise ReleaseError("NOT_VALID", f"{len(problems)} problems with --release (proposed errata count): {shown}")
    log = (root / CHANGELOG).read_text(encoding="utf-8")
    start, end = _unreleased(log)
    body = log[start + len(UNRELEASED):end]
    if not body.strip():
        raise ReleaseError("EMPTY_UNRELEASED", f"'{UNRELEASED}' in {CHANGELOG} is empty")
    if workbooks is None and not allow_no_workbooks:
        raise ReleaseError("NO_WORKBOOKS", "give --workbooks DIR for the determinism check, or --no-workbooks")
    differ = determinism(root, workbooks)
    if differ:
        raise ReleaseError("NOT_DETERMINISTIC", f"generated files differ: {', '.join(differ[:5])}")

    texts = _rewrite_all(root, "main", version)
    _check_hashes(root, texts)
    writes = dict(texts)
    schemas = sorted((root / "schemas").rglob("*.json"))
    for p in schemas:
        writes[root / "tools" / "schemas" / version / p.relative_to(root / "schemas")] = texts.get(p) or p.read_text(encoding="utf-8")
    added, changed, removed = change_list(root, tags[-1] if tags else None)
    note = "" if workbooks is not None else "The workbook determinism check (tools.extract_xlsx --check) was skipped.\n\n"
    generated = _section("Added", added) + _section("Changed", changed) + _section("Removed", removed)
    release = (f"## {version} ({today.isoformat()})" + body.rstrip("\n") + "\n\n" + note
               + (f"### Models and libraries against {tags[-1]}\n\n" if tags else "### Models and libraries\n\n")
               + generated)
    writes[root / CHANGELOG] = log[:start] + release + log[end:]
    apply(writes)
    return CutReport(version, len(texts), len(schemas), added, changed, removed)


def reopen(root: Path) -> int:
    """Point every file back at main and open an empty Unreleased section; 0 (and nothing written) when the tree is
    already at main."""
    root = Path(root)
    release = tree_release(root)
    if release == "main":
        print("the tree is at main already: nothing to reopen")
        return 0
    texts = _rewrite_all(root, release, "main")
    _check_hashes(root, texts)
    writes = dict(texts)
    log = (root / CHANGELOG).read_text(encoding="utf-8")
    if f"\n{UNRELEASED}\n" not in log:
        first = log.find("\n## ")
        at = first + 1 if first >= 0 else len(log)
        writes[root / CHANGELOG] = log[:at] + f"{UNRELEASED}\n\n" + log[at:]
    apply(writes)
    return len(texts)


def check(root: Path, tag: str | None = None) -> list[str]:
    """Problems with the tree as a release (empty when none): every file at one release, which is `tag` when given; for
    a release other than main, tools/schemas/<release>/ equal to schemas/, a changelog section for it, and the
    validator clean with proposed errata counted."""
    from tools.validate import validate_repo
    root = Path(root)
    release = tree_release(root)
    problems = []
    seen = defaultdict(list)
    for p in _files(root):
        for r in set(_URL_RE.findall(p.read_text(encoding="utf-8"))):
            seen[r].append(p.relative_to(root).as_posix())
    for r, paths in sorted(seen.items()):
        if r != release:
            problems += [f"{path}: at release {r}, the tree is at {release}" for path in paths]
    if tag is not None and release != tag:
        problems.append(f"the tree is at release {release}, the tag is {tag}")
    if release == "main":
        return problems
    copy = root / "tools" / "schemas" / release
    if not copy.is_dir():
        problems.append(f"tools/schemas/{release}/ is missing")
    else:
        a = {p.relative_to(root / "schemas").as_posix(): p.read_bytes() for p in (root / "schemas").rglob("*.json")}
        b = {p.relative_to(copy).as_posix(): p.read_bytes() for p in copy.rglob("*.json")}
        problems += [f"tools/schemas/{release}/{k} differs from schemas/{k}" for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    if f"\n## {release} (" not in (root / CHANGELOG).read_text(encoding="utf-8"):
        problems.append(f"{CHANGELOG} has no section for {release}")
    problems += [f"{p.file}: {p.code}: {p.detail}" for p in validate_repo(root, registry_check=True)]
    return problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m tools.release")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("cut")
    c.add_argument("version")
    c.add_argument("--workbooks", type=Path)
    c.add_argument("--no-workbooks", action="store_true")
    sub.add_parser("reopen")
    k = sub.add_parser("check")
    k.add_argument("--tag")
    p.add_argument("--root", type=Path, default=ROOT)
    a = p.parse_args(argv)
    try:
        if a.command == "cut":
            r = cut(a.root, a.version, date.today(), a.workbooks, a.no_workbooks)
            print(f"cut {r.version}: {r.files_rewritten} files rewritten, {r.schemas_copied} schemas copied; "
                  f"{len(r.added)} added, {len(r.changed)} changed, {len(r.removed)} removed")
            return 0
        if a.command == "reopen":
            print(f"reopened: {reopen(a.root)} files rewritten")
            return 0
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    problems = check(a.root, a.tag)
    for line in problems:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
