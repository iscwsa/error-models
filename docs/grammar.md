> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Formula grammar

Formulas are the VBA-style expressions in the `Depth Formula`, `Inclination Formula`, `Azimuth Formula` and
`Singularity * Formula` columns of the ISCWSA error-model spreadsheets. The reference implementation is
`tools/formula.py` (hand-written tokenizer and recursive-descent parser; formulas are never passed to `eval`).

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
| `Az` | rad | azimuth as written in the sheets' singularity formulas (Rev5 ABXY-TI2 singularity_north/east) and in the ISCWSA MWD bias Rev0 terms (with TF); whether it is true or magnetic azimuth is not yet decided (Plan 2, from SPE 67616 and the Rev5 definition); kept as its own variable so the published text is unchanged |
| `MD`, `TVD`, `MDPrev` | m | |
| `BField` | nT | |
| `GField` | m/s^2 | |
| `EarthRate` | rad/s | |
| `XCLTortuosity` | rad per m | the unit the main XCLA / XCLH text needs (it is compared with radians). The model parameter stays `{"value": 1, "unit": "deg/100ft"}` and an engine converts it (1 deg/100 ft = pi/180/30.48 rad/m). The sheet's XCLA singularity text multiplies it by `RAD` as if it were deg per m; that is a proposed erratum (`tools/errata.json`) |
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
environment raises (`FormulaError`).
