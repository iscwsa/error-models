# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Formula grammar for ISCWSA error-model term expressions.

Hand-written tokenizer and recursive-descent parser for the VBA-style
expressions used in the spreadsheets. Formulas are never passed to eval.
See docs/grammar.md for the grammar.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

ALIASES: dict[str, str] = {
    "Sqr": "Sqrt",
    "sqrt": "Sqrt",
    "Gfield": "GField",
    "Bfield": "BField",
    "pi": "Pi",
    "Latitude": "Lat",
}
FUNCTIONS = {"Sin", "Cos", "Tan", "Abs", "Sqrt", "Max", "Min"}
CONSTANTS = {"Pi": math.pi, "RAD": math.pi / 180}
VARIABLES: frozenset[str] = frozenset(
    "Inc Az AzT AzM MD TVD TF MDPrev IncPrev AzPrev Dip BField GField Lat EarthRate "
    "XCLTortuosity NoiseReductionFactor GXYRunningSpeed GZRunningSpeed "
    "XY_Gyro_Drift XY_Gyro_Random_Walk Z_Gyro_Drift".split()
)
_MIN_ARGS = {"Sin": 1, "Cos": 1, "Tan": 1, "Abs": 1, "Sqrt": 1, "Max": 2, "Min": 2}
_MAX_ARGS = {"Sin": 1, "Cos": 1, "Tan": 1, "Abs": 1, "Sqrt": 1}


class FormulaError(ValueError):
    def __init__(self, message: str, position: int = 0):
        super().__init__(f"{message} (at position {position})")
        self.position = position


# ---------------------------------------------------------------- tokenizer
_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
    r"|(?P<id>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op>[-+*/^(),]))"
)


def _tokenize(text: str) -> list[tuple[str, str, int]]:
    toks: list[tuple[str, str, int]] = []
    pos = 0
    n = len(text)
    while True:
        m = _TOKEN.match(text, pos)
        if m is None:
            if text[pos:].strip() == "":
                break
            bad = pos + (len(text[pos:]) - len(text[pos:].lstrip()))
            raise FormulaError(f"unexpected character {text[bad]!r}", bad)
        kind = m.lastgroup
        value = m.group(kind)
        start = m.start(kind)
        if kind == "id":
            value = ALIASES.get(value, value)
        toks.append((kind, value, start))
        pos = m.end()
        if pos >= n:
            break
    toks.append(("end", "", n))
    return toks


# ---------------------------------------------------------------- nodes
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "neg": 3, "^": 4, "atom": 5}


def _div(a: float, b: float) -> float:
    if b == 0:
        if a == 0 or a != a:
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def _is_odd_int(x: float) -> bool:
    return math.isfinite(x) and x == math.floor(x) and math.fmod(x, 2) != 0


def _pow(a: float, b: float) -> float:
    try:
        return math.pow(a, b)
    except ValueError:
        if a == 0 and b < 0:
            return -math.inf if (math.copysign(1.0, a) < 0 and _is_odd_int(b)) else math.inf
        return math.nan
    except OverflowError:
        return -math.inf if (a < 0 and _is_odd_int(b)) else math.inf


def _fn1(f):
    def g(x: float) -> float:
        try:
            return f(x)
        except (ValueError, OverflowError):
            return math.nan

    return g


def _maxmin(f):
    def g(*xs: float) -> float:
        if any(x != x for x in xs):
            return math.nan
        return f(xs)

    return g


_FUNC_IMPL = {
    "Sin": _fn1(math.sin),
    "Cos": _fn1(math.cos),
    "Tan": _fn1(math.tan),
    "Abs": _fn1(abs),
    "Sqrt": _fn1(math.sqrt),
    "Max": _maxmin(max),
    "Min": _maxmin(min),
}


class Node:
    prec = _PREC["atom"]

    def evaluate(self, env: Mapping[str, float]) -> float:
        raise NotImplementedError

    def identifiers(self) -> frozenset[str]:
        return frozenset()

    def render(self) -> str:
        raise NotImplementedError

    def _wrap(self, child: "Node", min_prec: int) -> str:
        s = child.render()
        return s if child.prec >= min_prec else f"({s})"


@dataclass(frozen=True)
class Num(Node):
    value: float

    def evaluate(self, env):
        return self.value

    def render(self):
        v = self.value
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return repr(v)


@dataclass(frozen=True)
class Const(Node):
    name: str

    def evaluate(self, env):
        return CONSTANTS[self.name]

    def render(self):
        return self.name


@dataclass(frozen=True)
class Var(Node):
    name: str
    position: int = 0

    def evaluate(self, env):
        try:
            return float(env[self.name])
        except KeyError:
            raise FormulaError(f"variable {self.name!r} not in environment", self.position) from None

    def identifiers(self):
        return frozenset({self.name})

    def render(self):
        return self.name


@dataclass(frozen=True)
class Neg(Node):
    operand: Node
    prec = _PREC["neg"]

    def evaluate(self, env):
        return -self.operand.evaluate(env)

    def identifiers(self):
        return self.operand.identifiers()

    def render(self):
        return "-" + self._wrap(self.operand, _PREC["neg"])


@dataclass(frozen=True)
class Bin(Node):
    op: str
    left: Node
    right: Node

    @property
    def prec(self):  # type: ignore[override]
        return _PREC[self.op]

    def evaluate(self, env):
        a = self.left.evaluate(env)
        b = self.right.evaluate(env)
        op = self.op
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return _div(a, b)
        return _pow(a, b)

    def identifiers(self):
        return self.left.identifiers() | self.right.identifiers()

    def render(self):
        p = self.prec
        if self.op == "^":
            # base must be atomic; exponent atomic or a negated atom
            left = self._wrap(self.left, _PREC["atom"])
            r = self.right
            if isinstance(r, Neg) and r.operand.prec == _PREC["atom"]:
                right = r.render()
            else:
                right = self._wrap(r, _PREC["atom"])
            return f"{left} ^ {right}"
        # left-associative: right operand of equal precedence keeps parentheses
        return f"{self._wrap(self.left, p)} {self.op} {self._wrap(self.right, p + 1)}"


@dataclass(frozen=True)
class Call(Node):
    name: str
    args: tuple

    def evaluate(self, env):
        return _FUNC_IMPL[self.name](*[a.evaluate(env) for a in self.args])

    def identifiers(self):
        out: frozenset[str] = frozenset()
        for a in self.args:
            out |= a.identifiers()
        return out

    def render(self):
        return f"{self.name}({', '.join(a.render() for a in self.args)})"


# ---------------------------------------------------------------- parser
class _Parser:
    def __init__(self, text: str, allowed):
        self.toks = _tokenize(text)
        self.i = 0
        self.allowed = allowed

    def peek(self):
        return self.toks[self.i]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, value: str):
        k, v, p = self.peek()
        if k != "op" or v != value:
            raise FormulaError(f"expected {value!r}", p)
        self.i += 1

    def parse(self) -> Node:
        node = self.expr()
        k, v, p = self.peek()
        if k != "end":
            raise FormulaError(f"unexpected {v!r}", p)
        return node

    def expr(self) -> Node:
        node = self.term()
        while True:
            k, v, _ = self.peek()
            if k == "op" and v in "+-":
                self.i += 1
                node = Bin(v, node, self.term())
            else:
                return node

    def term(self) -> Node:
        node = self.unary()
        while True:
            k, v, _ = self.peek()
            if k == "op" and v in "*/":
                self.i += 1
                node = Bin(v, node, self.unary())
            else:
                return node

    def unary(self) -> Node:
        k, v, _ = self.peek()
        if k == "op" and v in "+-":
            self.i += 1
            operand = self.unary()
            return Neg(operand) if v == "-" else operand
        return self.power()

    def power(self) -> Node:
        base = self.primary()
        k, v, _ = self.peek()
        if k == "op" and v == "^":
            self.i += 1
            k2, v2, _ = self.peek()
            if k2 == "op" and v2 in "+-":
                self.i += 1
                exp = self.primary()
                if v2 == "-":
                    exp = Neg(exp)
            else:
                exp = self.primary()
            k3, v3, p3 = self.peek()
            if k3 == "op" and v3 == "^":
                raise FormulaError("chained '^' is not allowed; use parentheses", p3)
            return Bin("^", base, exp)
        return base

    def primary(self) -> Node:
        k, v, p = self.next()
        if k == "num":
            return Num(float(v))
        if k == "op" and v == "(":
            node = self.expr()
            self.expect(")")
            return node
        if k == "id":
            nk, nv, _ = self.peek()
            is_call = nk == "op" and nv == "("
            if v in FUNCTIONS:
                if not is_call:
                    raise FormulaError(f"function {v!r} requires arguments", p)
                self.i += 1
                args = [self.expr()]
                while self.peek()[:2] == ("op", ","):
                    self.i += 1
                    args.append(self.expr())
                self.expect(")")
                if len(args) < _MIN_ARGS[v] or len(args) > _MAX_ARGS.get(v, 10**9):
                    raise FormulaError(f"wrong number of arguments for {v}", p)
                return Call(v, tuple(args))
            if is_call:
                raise FormulaError(f"unknown function {v!r}", p)
            if v in CONSTANTS:
                return Const(v)
            if self.allowed is not None and v not in self.allowed:
                raise FormulaError(f"unknown identifier {v!r}", p)
            return Var(v, p)
        raise FormulaError(f"unexpected {v!r}" if k != "end" else "unexpected end of formula", p)


def parse(text: str, allowed: frozenset[str] | None = None) -> Node:
    return _Parser(text, allowed).parse()


def canonical(text: str) -> str:
    return parse(text).render()
