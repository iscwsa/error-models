> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Formula grammar

Formulas are the VBA-style expressions in the `Depth Formula`, `Inclination Formula`, `Azimuth Formula` and
`Singularity * Formula` columns of the ISCWSA error-model spreadsheets. The reference parser and evaluator is
`tools/formula.py` (hand-written tokenizer and recursive-descent parser; formulas are never passed to `eval`). The reference
loader (which reads a model, applies its `requires` and converts the parameter units) is not in this repository: it lives in
the private DGI engine check.

## EBNF

```ebnf
formula    = expr ;
expr       = term , { ( "+" | "-" ) , term } ;
term       = unary , { ( "*" | "/" ) , unary } ;
unary      = ( "-" | "+" ) , unary | power ;
power      = primary , [ "^" , [ "-" | "+" ] , primary ] ;
primary    = number | constant | variable | call | "(" , expr , ")" ;
call       = function , "(" , expr , { "," , expr } , ")" ;
number     = digits , [ "." , [ digits ] ] , [ exponent ] | "." , digits , [ exponent ] ;
exponent   = ( "e" | "E" ) , [ "+" | "-" ] , digits ;
identifier = ( letter | "_" ) , { letter | digit | "_" } ;
```

Whitespace between tokens is insignificant. `function`, `constant` and `variable` are identifiers (after
aliasing) from the tables below; a function name must be followed by `(`, and `variable` names must not be.
Names are case-sensitive; the only alternative spellings are the aliases below.

## Precedence (highest first)

| Level | Operator | Associativity |
|-------|----------|---------------|
| 1 | `^` (power) | none: `2^3^2` is an error, write `2^(3^2)` or `(2^3)^2` |
| 2 | unary `-`, `+` | prefix; binds looser than `^`, so `-2^2 = -4` |
| 3 | `*`, `/` | left |
| 4 | `+`, `-` | left |

The exponent of `^` may carry one sign (`2 ^ -2`). A parenthesised base is fine: `(Sin(Inc))^0.25`.

## Functions

| Name | Arguments | Meaning |
|------|-----------|---------|
| `Sin`, `Cos`, `Tan` | 1 | trigonometric, argument in radians |
| `Abs` | 1 | absolute value |
| `Sqrt` | 1 | square root |
| `Max`, `Min` | 2 or more | largest / smallest argument |

## Constants

| Name | Value |
|------|-------|
| `Pi` | pi |
| `RAD` | pi / 180 (degrees to radians) |

## Variables

| Name | Unit | Notes |
|------|------|-------|
| `Inc`, `AzT`, `AzM`, `TF`, `Dip`, `Lat`, `IncPrev`, `AzPrev` | rad | |
| `Az` | rad | the station's recorded azimuth (true), as the 806 diagnostics require: `Az` is the same quantity as `AzT`. Kept as its own variable so the published sheet text is unchanged. It appears in the singularity formulas of ABXY-TI2/ABIXY-TI2 (`iscwsa:rev3`-`rev5`), in CNA, XCLA and XCLH (`iscwsa:rev5`), and in the sensor terms of `iscwsa:rev0`-`rev2` (as `Az + TF`). Only ABXY-TI2S is exercised by a published diagnostic (with `AzM` instead, 416 of 541 stations fail; with `AzT`, all 541 pass); the others follow the same reading. Discrepancies listed for the sub-committee: Rev 5.13 §11.5 writes `Am` (magnetic) in the ABXY-TI2 vertical row, and the RCS sheet (library `iscwsa:rot6axis`) writes `AzM` in ABXY-TI2. See C4 in [`deviations.md`](deviations.md) |
| `MD`, `TVD`, `MDPrev` | m | |
| `BField` | nT | |
| `GField` | m/s^2 | |
| `EarthRate` | rad/s | |
| `XCLTortuosity` | rad per m | the unit the main XCLA / XCLH text needs (it is compared with radians). The model parameter stays `{"value": 1, "unit": "deg/100ft"}` and an engine converts it (1 deg/100 ft = pi/180/30.48 rad/m). The private engine's loader converts the units `deg/100ft`, `deg/30m`, `deg/100m` and `deg/m` and refuses any other. The sheet's XCLA singularity text multiplies it by `RAD` as if it were deg per m; that is a proposed erratum (`tools/errata.json`, rows E5 and E6 of [`deviations.md`](deviations.md)) |
| `NoiseReductionFactor`, `GXYRunningSpeed`, `GZRunningSpeed`, `XY_Gyro_Drift`, `XY_Gyro_Random_Walk`, `Z_Gyro_Drift` | as defined by the model | |

## Aliases

Applied at tokenization, so canonical text only ever contains the canonical name.

| Sheet spelling | Canonical |
|----------------|-----------|
| `Sqr`, `sqrt` | `Sqrt` |
| `Gfield` | `GField` |
| `Bfield` | `BField` |
| `pi` | `Pi` |
| `Latitude` | `Lat` |

## Canonical text

`canonical(text)` re-renders with canonical names, single spaces around binary operators (none after unary
minus), `, ` between arguments, and the minimal parentheses that preserve the parse tree (so `1 - (2 - 3)` and
`(2^3)^2` keep theirs). Numbers are normalised (`1.0` becomes `1`).

## Undefined results

Evaluation follows IEEE 754 and never raises: `x / 0` gives `+inf` or `-inf` (by the signs of x and the zero), and
`0 / 0` gives `NaN`. Domain errors (`Sqrt` of a negative, `Sin(inf)`, a negative base to a fractional power) give
`NaN`; overflow gives `+inf`/`-inf`. `Max`/`Min` return `NaN` if any argument is `NaN`. Consumers must treat a
non-finite result as "undefined at this survey station" rather than as an error. Only a variable missing from the
environment raises (`FormulaError`). Where a formula is undefined at a vertical station, the library may carry singularity formulas; how an engine treats vertical stations is provisional, see the "Vertical stations" section of [`conformance.md`](conformance.md).

## Limits

Digits are ASCII `0-9` only (other Unicode digits are rejected). A number literal must be finite: `1e999` is a
`FormulaError`. Nesting of parentheses, function calls and unary signs is capped at depth 200; deeper input raises
`FormulaError` (positioned at the offending token) rather than `RecursionError`.
