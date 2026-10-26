# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The README status table and the changelog against the files they describe."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _status_section():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return text.split("### MODEL STATUS", 1)[1].split("\n---", 1)[0]


def _status_lines(text):
    """The table rows and the two summary lines of a status listing."""
    return [ln.rstrip() for ln in text.splitlines() if ln.startswith("|") or re.match(r"\d+ (reference )?models?:", ln)]


def _rows(section):
    return [[c.strip() for c in r.strip().strip("|").split("|")]
            for r in section.splitlines() if re.match(r"\| [a-z_]+:\S+ \|", r)]


def _on_disk(*parts):
    ids = set()
    for path in (ROOT.joinpath(*parts)).glob("*/*.json"):
        ids.add(json.loads(path.read_text(encoding="utf-8"))["metadata"]["model_id"])
    return ids


def test_status_table_lists_every_model():
    cells = _rows(_status_section())
    ids = [c[0] for c in cells]
    assert len(ids) == len(set(ids)) == 129 + 6
    assert set(ids) == _on_disk("models") | _on_disk("conformance", "models")
    assert len(_on_disk("models")) == 129 and len(_on_disk("conformance", "models")) == 6


def test_status_table_counts():
    cells = _rows(_status_section())
    models = [c for c in cells if c[3] != "reference"]
    assert sum(1 for c in models if c[4] == "loaded") == 124
    assert sum(1 for c in models if c[4].startswith("refused")) == 5
    assert sum(1 for c in models if c[6] == "19476/19476") == 2
    assert not any(c[4].startswith("refused") and "gyro_modes" in c[4] for c in models)


def test_status_table_matches():
    """The README tables are the engine's status listing, copied unchanged (tests/fixtures/status_tables.md)."""
    expected = (ROOT / "tests" / "fixtures" / "status_tables.md").read_text(encoding="utf-8")
    assert _status_lines(_status_section()) == _status_lines(expected)
    assert len(_status_lines(expected)) > 130


def test_changelog_lists_every_erratum():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased" in changelog
    for e in json.loads((ROOT / "tools" / "errata.json").read_text(encoding="utf-8")):
        row = f"| `{e['library']}` {e['weighting_function']} {e['field']} | {e['status']} |"
        assert row in changelog, row


def test_no_internal_names_or_stale_wording():
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", *(ROOT / "docs").glob("*.md")]
    for f in files:
        assert not re.search(r"\b(Plan|Task) \d", f.read_text(encoding="utf-8")), f
    this = Path(__file__).resolve()
    label = re.compile(r"\b(?:Plan|Task) " + r"[0-9]|(?<![\w-])G" + r"[0-9]+\b")
    for f in [*(ROOT / "tools").glob("*.py"), *(ROOT / "tests").glob("*.py")]:
        if f.resolve() != this:
            assert not label.search(f.read_text(encoding="utf-8")), f
    assert "finding under review" not in (ROOT / "tools" / "errata.json").read_text(encoding="utf-8")


def test_grammar_lists_gyro_variables():
    from tools.formula import ACCUMULATORS
    text = (ROOT / "docs" / "grammar.md").read_text(encoding="utf-8")
    section = text.split("## Variables", 1)[1].split("## Aliases", 1)[0]
    rows = {m.group(1) for row in section.splitlines() if row.startswith("|")
            for m in re.finditer(r"`([A-Za-z_]+)`", row.split("|")[1])}
    for name in [*ACCUMULATORS, "GXYRunningSpeed", "GZRunningSpeed", "GXYZRunningSpeed", "NoiseReductionFactor", "IncCant"]:
        assert name in rows, name
    assert "init_factor" in section and "SPE 90408" in section


def test_conformance_doc_lists_kinds():
    text = (ROOT / "docs" / "conformance.md").read_text(encoding="utf-8")
    for kind in ("per_term_nev", "total_nev", "hla"):
        assert f"`{kind}`" in text
    assert "zero_uncertainty" in text
    assert "known_misses" in text
    assert "Known misses" in text


def _propagation():
    return (ROOT / "docs" / "propagation.md").read_text(encoding="utf-8")


def test_propagation_sections():
    headings = re.findall(r"^## (.+)$", _propagation(), re.M)
    assert headings == [
        "The position derivative",
        "Random, systematic, well and global terms",
        "The tie-on",
        "Vertical stations",
        "Toolface of the Rev0-2 sensor terms",
        "Position-direct XCLA and XCLH",
        "Gyro survey modes",
        "Bias terms",
        "Uncertainty at an assigned depth",
    ]


def test_every_convention_has_count():
    """Each rule labelled `Convention C<n>` has a row in deviations.md with a positive integer failing count. Each
    `Open reading ... (C<n>)` (a rule the printed values do not decide) has a row."""
    text = _propagation()
    deviations = (ROOT / "docs" / "deviations.md").read_text(encoding="utf-8")
    rows = {}
    for line in deviations.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| C") and len(cells) >= 5:
            rows[cells[0]] = cells
    words = re.findall(r"\b[Cc]onvention\b(?: (C\d+))?", text)
    assert len(words) >= 8
    assert all(words), "a rule says convention without naming its deviations.md row"
    for row_id in words:
        assert row_id in rows, row_id
        assert re.match(r"[1-9]\d*\b", rows[row_id][4]), (row_id, rows[row_id][4])
    opened = re.findall(r"Open reading[^()*]*[(](C\d+)[)]", text)
    for row_id in opened:
        assert row_id in rows, row_id
    assert {"C13", "C16", "C17", "C18", "C19", "C20", "C22", "C23", "C27", "C28"} <= set(words)
    assert {"C15", "C21"} <= set(opened)
    assert not {"C15", "C21"} & set(words)


def test_deviations_rows_for_gyro():
    deviations = (ROOT / "docs" / "deviations.md").read_text(encoding="utf-8")
    for needle in ("Table 10", "known miss", "`init_inc`", "provisional", "67616"):
        assert needle in deviations, needle
    assert "planned" not in deviations and "(planned)" not in deviations


def test_no_internal_labels():
    """No document or Python file carries a plan, task or decision label; term names such as GXY-G1 are fine."""
    label = re.compile(r"\b(?:Plan|Task) " + r"[0-9]|(?<![\w-])G" + r"[0-9]+\b")
    files = [ROOT / "README.md", ROOT / "CHANGELOG.md", *(ROOT / "docs").glob("*.md"),
             *(ROOT / "tools").glob("*.py"), *(ROOT / "tests").glob("*.py")]
    me = Path(__file__).resolve()
    for f in files:
        if f.resolve() != me:
            m = label.search(f.read_text(encoding="utf-8"))
            assert not m, (f, m.group(0))


def test_stale_wording_gone():
    conformance = (ROOT / "docs" / "conformance.md").read_text(encoding="utf-8")
    assert "not yet available" not in conformance and "propagation.md" in conformance
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "not yet supported" not in readme and "propagation.md" in readme
    assert "pending" not in readme.split("### MODEL STATUS", 1)[1].split("\n---", 1)[0].lower().replace("sub-committee", "")
