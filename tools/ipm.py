# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Compass IPM text: parser, and the translation of IPM formulas to and from the formula grammar (docs/ipm.md).

An IPM row is Name / Vector / Tie-on / Unit / Value / Formula [/ Start Inc / End Inc], tab-separated. Formulas are in
radians and feet. Only a subset is translated (docs/ipm.md, "Subset"); anything else raises IpmError naming the
construct. Formulas are never passed to eval: the text is tokenized here and parsed by tools/formula.py.

Two readings of an IPM formula (docs/ipm.md, "Constants"):
  literal   the IPM meaning exactly: lengths in feet (`tmd` = MD * 3.280839895013123), `erot` in rad/hr
  natural   lengths in metres (`tmd` = MD, `mtf` = 1) and `erot` = EarthRate * Cos(Lat) in rad/s; equal to the literal
            reading only for a dimensionally consistent row, which tools/ipm2json checks numerically
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.formula import Bin, Call, Const, FormulaError, Neg, Node, Num, Var, parse

FT = 0.3048
MTF = 1 / FT  # 3.280839895013123 feet per metre, the guide's `mtf`
RAD = math.pi / 180
# Unit column -> factor on Value (the guide's "Units"); any other unit has factor 1
UNIT_FACTORS: dict[str, float] = {"m": MTF, "im": FT, "i": FT, "d": RAD, "dnt": RAD, "t": 0.001}
# Unit column -> the term's units in the JSON library; 't' (thousandths) becomes '-' with the factor in the magnitude
JSON_UNITS: dict[str, str] = {"-": "-", "m": "m", "im": "1/m", "i": "1/m", "d": "deg", "dnt": "deg.nT", "nt": "nT",
                              "t": "-"}
# JSON units -> factor to SI (radians, metres, seconds), as an engine converts a magnitude
SI: dict[str, float] = {"-": 1.0, "m": 1.0, "1/m": 1.0, "m/s2": 1.0, "nT": 1.0, "deg": RAD, "deg.nT": RAD,
                        "deg/hr": RAD / 3600, "deg/sqr(hr)": RAD / 60}
VECTORS = ("e", "s", "i", "a", "l", "x", "y")
TIE_ONS = {"r": "Random", "s": "Systematic", "w": "Well", "g": "Global"}
FUNCTIONS = {"sin": "Sin", "cos": "Cos", "tan": "Tan", "abs": "Abs", "sqrt": "Sqrt", "sqr": "Sqrt", "max": "Max",
             "min": "Min"}
_L = "(MD - MDPrev)"
LITERAL: dict[str, str] = {
    "inc": "Inc", "azt": "AzT", "azm": "AzM", "dip": "Dip", "lat": "Lat", "pi": "Pi", "dtr": "RAD", "tfo": "TF",
    "mtot": "BField", "gtot": "GField", "din": "(Inc - IncPrev)", "daz": "(AzT - AzPrev)", "tho": "0.001",
    "mtf": repr(MTF), "smd": f"{_L} * {MTF!r}", "tmd": f"MD * {MTF!r}", "tvd": f"TVD * {MTF!r}",
    "erot": "(3600 * EarthRate * Cos(Lat))",
}
NATURAL: dict[str, str] = dict(LITERAL, mtf="1", smd=_L, tmd="MD", tvd="TVD", erot="(EarthRate * Cos(Lat))")
_LENGTHS = {"smd": _L, "tmd": "MD", "tvd": "TVD"}  # `<length>/mtf` is that length in metres, in either reading
_TOKEN = re.compile(r"\s*(?:(?P<num>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)|(?P<id>[A-Za-z_][A-Za-z_0-9]*)"
                    r"|(?P<op>[-+*/^(),]))")


class IpmError(ValueError):
    """An IPM construct outside the translated subset, named by its class (docs/ipm.md, "Not converted")."""

    def __init__(self, construct: str, row: "IpmRow | None" = None, detail: str = ""):
        where = f" (line {row.line}, {row.name!r})" if row is not None else ""
        super().__init__(f"{construct}{where}{': ' + detail if detail else ''}")
        self.construct, self.row = construct, row


@dataclass(frozen=True)
class IpmRow:
    name: str
    vector: str
    tie_on: str
    unit: str
    value: float
    formula: str
    start_inc: float | None
    end_inc: float | None
    line: int


@dataclass
class IpmFile:
    header: dict[str, str] = field(default_factory=dict)
    rows: list[IpmRow] = field(default_factory=list)
    file: str = "ipm"   # the file name (read_ipm), for the model's origin
    sha256: str = ""    # of the file's bytes (read_ipm), or of the text as UTF-8 (parse_ipm)
    layout: bool = False  # a column-title line Name / Vector / Tie-On / Unit ... (with or without '#') was seen


_TITLE = ["name", "vector", "tie-on", "unit"]


def is_variable(row: IpmRow) -> bool:
    """The guide marks a variable with Vector and Tie-on 'n'; some older files with Tie-on 'n' alone."""
    return row.vector == "n" or row.tie_on == "n"


def parse_ipm(text: str) -> IpmFile:
    out = IpmFile(sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    for n, line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if [x.strip().lower() for x in line.lstrip("#").split("\t")[:4]] == _TITLE:
            out.layout = True
        if line.startswith("#"):
            key, _, value = line[1:].partition(":")
            out.header[key.strip()] = value.strip()
            continue
        f = [x.strip() for x in line.split("\t")]
        if len(f) < 6 or not f[0] or f[0].lower() == "name" or len(f[1]) != 1 or len(f[2]) != 1:
            continue  # not a row: the column titles, a blank or a comment line
        try:
            value = float(f[4])
            lo = float(f[6]) if len(f) > 6 and f[6] else None
            hi = float(f[7]) if len(f) > 7 and f[7] else None
        except ValueError:
            raise IpmError("syntax", None, f"line {n}: a number column is not a number") from None
        if lo == 0.0 and hi == 0.0:  # 0 / 0 is written for "no range"
            lo = hi = None
        out.rows.append(IpmRow(f[0], f[1].lower(), f[2].lower(), f[3].lower(), value, f[5], lo, hi, n))
    return out


def read_ipm(path) -> IpmFile:
    data = Path(path).read_bytes()
    if b"\x00" in data:
        raise IpmError("binary", None, f"{path} is not a text file")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            raise IpmError("encoding", None, f"{path} is neither UTF-8 nor cp1252") from None
    out = parse_ipm(text)
    out.file, out.sha256 = Path(path).name, hashlib.sha256(data).hexdigest()
    return out


# ---------------------------------------------------------------- IPM -> grammar
def _grammar_text(formula: str, variables, row) -> str:
    """The IPM text with IPM names replaced by placeholders (`ipm_<name>`) and functions by the grammar's names."""
    out, pos = [], 0
    toks = []
    while pos < len(formula):
        m = _TOKEN.match(formula, pos)
        if m is None:
            if formula[pos:].strip() == "":
                break
            raise IpmError("syntax", row, f"unexpected {formula[pos:].strip()[0]!r} in {formula!r}")
        toks.append((m.lastgroup, m.group(m.lastgroup)))
        pos = m.end()
    for i, (kind, v) in enumerate(toks):
        if kind != "id":
            out.append(v)
            continue
        name = v.lower()
        if i + 1 < len(toks) and toks[i + 1] == ("op", "("):
            if name not in FUNCTIONS:
                raise IpmError(f"function:{name.upper()}", row)
            out.append(FUNCTIONS[name])
        elif name in variables:
            raise IpmError("variable", row, name)
        elif name in LITERAL:
            out.append(f"ipm_{name}")
        else:
            raise IpmError(f"constant:{name}", row)
    return " ".join(out)


_ONE = Num(1.0)  # the natural reading's `mtf`: simplified away where it multiplies or divides


def _sub(table: dict[str, Node], node: Node) -> Node:
    if isinstance(node, Var) and node.name.startswith("ipm_"):
        return table[node.name[4:]]
    if isinstance(node, Bin):
        if (node.op == "/" and isinstance(node.left, Var) and node.left.name[4:] in _LENGTHS
                and isinstance(node.right, Var) and node.right.name == "ipm_mtf"):
            return parse(_LENGTHS[node.left.name[4:]])
        a, b = _sub(table, node.left), _sub(table, node.right)
        if node.op in "*/" and b is _ONE:
            return a
        if node.op == "*" and a is _ONE:
            return b
        return Bin(node.op, a, b)
    if isinstance(node, Neg):
        return Neg(_sub(table, node.operand))
    if isinstance(node, Call):
        return Call(node.name, tuple(_sub(table, a) for a in node.args))
    return node


def _tables():
    lit = {k: parse(v) for k, v in LITERAL.items()}
    nat = {k: parse(v) for k, v in NATURAL.items()}
    nat["mtf"] = _ONE
    return {"literal": lit, "natural": nat}


_TABLES = _tables()


def translate_node(formula: str, reading: str = "literal", variables=frozenset(), row: IpmRow | None = None) -> Node:
    text = _grammar_text(formula, variables, row)
    try:
        node = parse(text)
    except FormulaError as exc:
        raise IpmError("syntax", row, f"{formula!r}: {exc}") from None
    return _sub(_TABLES[reading], node)


def translate(formula: str, reading: str = "literal", variables=frozenset(), row: IpmRow | None = None) -> str:
    """Canonical grammar text of an IPM formula. `variables` are the file's variable names (refused: I1)."""
    return translate_node(formula, reading, variables, row).render()


# ---------------------------------------------------------------- grammar -> IPM
_VAR_TO_IPM = {"Inc": "inc", "AzT": "azt", "AzM": "azm", "Dip": "dip", "Lat": "lat", "TF": "tfo", "BField": "mtot",
               "GField": "gtot"}


def _is(node, name):
    return isinstance(node, Var) and node.name == name


def _inverse(node: Node, reading: str) -> Node:
    lit = reading == "literal"
    if isinstance(node, Bin):
        if node.op == "-" and _is(node.left, "MD") and _is(node.right, "MDPrev"):
            return Var("(smd/mtf)" if lit else "smd")
        if node.op == "-" and _is(node.left, "Inc") and _is(node.right, "IncPrev"):
            return Var("din")
        if node.op == "-" and _is(node.left, "AzT") and _is(node.right, "AzPrev"):
            return Var("daz")
        if (node.op == "*" and _is(node.left, "EarthRate") and isinstance(node.right, Call)
                and node.right.name == "Cos" and len(node.right.args) == 1 and _is(node.right.args[0], "Lat")):
            return Var("(erot/3600)" if lit else "erot")
        return Bin(node.op, _inverse(node.left, reading), _inverse(node.right, reading))
    if isinstance(node, Neg):
        return Neg(_inverse(node.operand, reading))
    if isinstance(node, Call):
        return Call(node.name.lower(), tuple(_inverse(a, reading) for a in node.args))
    if isinstance(node, Const):
        return Var({"Pi": "pi", "RAD": "dtr"}[node.name])
    if isinstance(node, Var):
        if node.name in ("MD", "TVD"):
            short = {"MD": "tmd", "TVD": "tvd"}[node.name]
            return Var(f"({short}/mtf)" if lit else short)
        if node.name in _VAR_TO_IPM:
            return Var(_VAR_TO_IPM[node.name])
        raise IpmError(f"variable:{node.name}")
    return node


def to_ipm(grammar_text: str, reading: str = "natural") -> str:
    """IPM formula text of a grammar formula (the inverse of `translate` in the same reading), or IpmError naming
    the first variable with no IPM equivalent (`variable:<name>`)."""
    try:
        node = parse(grammar_text)
    except FormulaError as exc:
        raise IpmError("syntax", None, str(exc)) from None
    return _inverse(node, reading).render().replace(" ", "")
