# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
import math
import os
from pathlib import Path

import pytest

from tools.formula import parse, canonical, FormulaError, VARIABLES


def ev(t, **env):
    return parse(t).evaluate(env)


def test_precedence_vba():
    assert ev("-2^2") == -4  # ^ binds tighter than unary minus
    assert ev("1 + 2 * 3 ^ 2") == 19


def test_chained_power_rejected():
    with pytest.raises(FormulaError):
        parse("2^3^2")


def test_aliases_canonicalise():
    assert canonical("Sqr(2) / Gfield + sqrt(Bfield) * pi") == "Sqrt(2) / GField + Sqrt(BField) * Pi"


def test_functions():
    assert ev("Max(1, Sqrt(10 / (MD - MDPrev)))", MD=12.5, MDPrev=10) == 2.0
    assert math.isclose(ev("Tan(90 * RAD - Inc)", Inc=math.radians(30)), 1 / math.tan(math.radians(30)))


def test_ieee_division():
    assert ev("1 / Sin(Inc)", Inc=0.0) == math.inf
    assert math.isnan(ev("0 / (MD - MDPrev)", MD=5, MDPrev=5))


def test_unknown_identifier_rejected_with_position():
    with pytest.raises(FormulaError) as e:
        parse("Cos(Incl)", allowed=VARIABLES)
    assert e.value.position == 4


def test_sheet_xym3e_text_parses():
    n = parse("Cos(Inc) * Cos(AzT)  * Max(1, sqrt(10/(MD-MDPrev)))", allowed=VARIABLES)
    assert n.identifiers() == {"Inc", "AzT", "MD", "MDPrev"}


def test_sheet_spellings():
    for t in ["(Sin(Inc))^0.25", "-(Cos(Inc) * Sin(Az+TF))", "-Sin(Az+TF)", "Latitude * pi",
              "Max(1,2)", "2 ^ -2", "Min(1, 2, 3)"]:
        parse(t, allowed=VARIABLES)
    assert ev("2 ^ -2") == 0.25
    assert ev("--3") == 3


def test_syntax_errors():
    for t in ["", "1 +", "(1", "1 2", "Sin()", "Sin(1, 2)", "Max(1)", "Foo(1)", "Sin", "Inc(1)", "1 $ 2", "1)", "2^3^2"]:
        with pytest.raises(FormulaError):
            parse(t)


def test_canonical_minimal_parens():
    assert canonical("(1 + 2) * 3") == "(1 + 2) * 3"
    assert canonical("((1 * 2)) + 3") == "1 * 2 + 3"
    assert canonical("1 - (2 - 3)") == "1 - (2 - 3)"
    assert canonical("(Sin(Inc))^0.25") == "Sin(Inc) ^ 0.25"
    assert canonical("(-2)^2") == "(-2) ^ 2"
    assert canonical("-(Cos(Inc)*2)") == "-(Cos(Inc) * 2)"
    assert canonical("-2^2") == "-2 ^ 2"
    assert canonical("(2^3)^2") == "(2 ^ 3) ^ 2"
    assert canonical("2^(3^2)") == "2 ^ (3 ^ 2)"
    for t in ["(2^3)^2", "1-(2-3)", "-(1+2)^2", "2^-(1+2)", "1/(2*3)", "a^(-b)"]:
        c = canonical(t)
        assert canonical(c) == c


def test_evaluate_never_raises():
    assert ev("1 / 0") == math.inf
    assert ev("-1 / 0") == -math.inf
    assert math.isnan(ev("Sqrt(-1)"))
    assert ev("0 ^ -1") == math.inf
    assert math.isnan(ev("(-8) ^ 0.5"))
    assert ev("10 ^ 1000") == math.inf
    assert math.isnan(ev("Sin(Inc)", Inc=math.inf))
    assert math.isnan(ev("Max(1, Inc)", Inc=math.nan))


def test_constants_not_identifiers():
    n = parse("Pi * RAD * Inc")
    assert n.identifiers() == {"Inc"}


def test_missing_variable():
    with pytest.raises(FormulaError):
        ev("Inc + 1")


@pytest.mark.skipif(not os.environ.get("ISCWSA_WORKBOOKS"), reason="workbooks not available")
def test_every_sheet_formula_parses():
    import openpyxl

    d = Path(os.environ["ISCWSA_WORKBOOKS"]).expanduser()
    names = [
        "iscwsa-mwd-error-models-rev5-23-sep-2022.xlsx",
        "toolgroup-owsg-a-rev-5-1-08-oct-2020-produced-23-sep-2022.xlsx",
        "toolgroup-owsg-b-rev-5-1-08-oct-2020-produced-23-sep-2022.xlsx",
        "iscwsa-rot-6axis-mwd-srgm-02jun2026.xlsx",
    ]
    heads = ["Depth Formula", "Inclination Formula", "Azimuth Formula",
             "Singularity North Formula", "Singularity East Formula", "Singularity Vert. Formula"]
    formulas = set()
    for n in names:
        wb = openpyxl.load_workbook(d / n, read_only=True, data_only=True)
        for ws in wb.worksheets:
            if ws.title in ("Index", "Sheet1", "Sheet2"):
                continue
            cols = None
            for row in ws.iter_rows(values_only=True):
                if cols is None:
                    if "Depth Formula" in row:
                        cols = [row.index(h) for h in heads if h in row]
                    continue
                for c in cols:
                    if c < len(row) and isinstance(row[c], str) and row[c].strip():
                        formulas.add(row[c])
            assert cols, f"no term table in {n}:{ws.title}"
        wb.close()
    assert formulas
    for f in sorted(formulas):
        parse(f, allowed=VARIABLES)
    print(len(formulas), "distinct formulas")


def test_non_finite_literal_rejected():
    with pytest.raises(FormulaError) as ei:
        parse("1e999")
    assert ei.value.position == 0
    with pytest.raises(FormulaError):
        parse("2 + 1e999")


def test_deep_nesting_is_formula_error():
    with pytest.raises(FormulaError) as ei:
        parse("(" * 2000 + "1" + ")" * 2000)
    assert ei.value.position == 200  # the 201st opening parenthesis


def test_deep_nesting_unary_and_calls():
    with pytest.raises(FormulaError):
        parse("-(" * 2000 + "1" + ")" * 2000)
    with pytest.raises(FormulaError):
        parse("-" * 2000 + "1")
    with pytest.raises(FormulaError):
        parse("Sin(" * 2000 + "1" + ")" * 2000)


def test_nesting_at_cap_parses():
    assert parse("(" * 200 + "1" + ")" * 200).evaluate({}) == 1.0


def test_ascii_digits_only():
    with pytest.raises(FormulaError):
        parse("\u0661")
    with pytest.raises(FormulaError):
        parse("1.\u0661")
