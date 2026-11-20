> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# IPM conversion

`tools/ipm2json.py` turns a Compass IPM file into one model and, when needed, one vendor library. `tools/json2ipm.py`
writes IPM text from a model. Both cover the subset below and stop with an `IpmError` that names the construct on
anything else; `ipm2json` writes nothing unless the whole file converts and the output validates.

The format reference is Landmark's "Guide to IPM Definition Files in Compass" (sections "Error Grid ISCWSA",
"Constants used in Formulas", "Formula Functions Supported" and "IPM File Header Lines"). The guide and the 2025-07
SLB/Landmark IPM specification workbook are cited here only; they are not distributed with this repository.

The test fixtures in `tests/fixtures/ipm/` are written from public ISCWSA models or by hand. No vendor IPM is part of this
repository.

## Subset

- **Rows.** Tab-separated Name / Vector / Tie-on / Unit / Value / Formula. The rows of one name are one source. A file
  may be UTF-8 (with or without a byte-order mark) or cp1252, with LF or CRLF line endings; anything else is refused.
- **Vectors.** `e` (depth), `s` (subsea depth), `i` (inclination), `a` (azimuth), `l` (lateral), and `x`/`y` (the XCL
  lateral and high-side position terms). `s` rows are read only with `--subsea`, where they replace the `e` rows of the
  same name.
- **One row per vector per source.** `i` and `y` count as the same vector, and so do `a`, `l` and `x`.
- **No inclination range** (Start / End Inc).
- **Tie-ons** `r`, `s`, `w`, `g`: the propagation (Random, Systematic, Well, Global).
- **Plain variables** (Vector and Tie-on `n`), inlined where a source uses them (see "Variables").
- **Functions** `SIN COS TAN ABS SQRT SQR MAX MIN` (`SQR` is the square root, as in the guide's formulas).
- **Operators** `+ - * / ^`, and the constants below.

## Constants

IPM formulas work in radians and feet. Each formula has two readings:

- **literal**: the IPM meaning exactly, with lengths in feet;
- **natural**: lengths in metres (`mtf` is 1), as the ISCWSA library writes its formulas.

| IPM | literal | natural |
|-----|---------|---------|
| `inc`, `azt`, `azm`, `dip`, `lat`, `tfo` | `Inc`, `AzT`, `AzM`, `Dip`, `Lat`, `TF` | the same |
| `azi` | `AzT` | the same |
| `mtot`, `gtot` | `BField`, `GField` | the same |
| `pi`, `dtr`, `tho` | `Pi`, `RAD`, `0.001` | the same |
| `din`, `daz` | `Inc - IncPrev`, `AzT - AzPrev` | the same |
| `mtf` | `3.280839895013123` | `1` |
| `smd`, `tmd`, `tvd` | `(MD - MDPrev)`, `MD`, `TVD`, each times `3.280839895013123` | `(MD - MDPrev)`, `MD`, `TVD` |
| `smd/mtf`, `tmd/mtf`, `tvd/mtf` | `(MD - MDPrev)`, `MD`, `TVD` | the same |
| `erot` | `3600 * EarthRate * Cos(Lat)` (rad/hr) | `EarthRate * Cos(Lat)` (rad/s) |

- `ipm2json` takes the natural reading of a row when it equals the literal reading, times the row's unit factor, at every
  station of the three ISCWSA Rev 5.1 diagnostic wells (`conformance/vectors/iscwsa_rev5-1/`) to a relative 1e-12. That
  holds for a dimensionally consistent row (e.g. `tmd` with no unit, `tmd*tvd` in `im`). Otherwise it keeps the literal
  reading times its exact factor, e.g. `0.3048 * (MD * 3.280839895013123 * (MD * 3.280839895013123))` for `tmd*tmd`.
- `daz` assumes an azimuth change under 180°, as the XCL sheets do. It isn't wrapped, and nothing special happens after
  a vertical station; a reader of the IPM may do both.
- `azi` is the azimuth from the well's reporting reference. The conversion takes that reference as true north, so `azi`
  is `AzT`. For a well reported to grid north, `azi` is `AzT` minus the grid convergence; the grammar has no
  convergence, so such a formula is the IPM's only where the convergence is 0 or the formula doesn't change under a
  rotation of the azimuth (an equal-magnitude XYM3 / XYM4 pair, for example).
- `tfo` is the station's toolface `TF`. A reader that takes `tfo` as 0, as Compass's ISCWSA tools do, gives the same
  weights only for formulas without it.
- At exactly 90°, `Tan(Inc)` is a very large finite number in the grammar. An IPM reader may treat it as having no value.
- `erot`: the guide's Earth rate is 15.041 deg/hr; `EarthRate` is SPE 90408's 7.2921159e-5 rad/s (15.0411 deg/hr). A
  converted formula with `erot` therefore differs from Compass's by 5e-6 relative.

## Variables

A variable row (Vector `n`, Tie-on `n`, or Tie-on `n` alone as in some older files) defines a name that later formulas
use. A plain variable is a shorthand: its value at a station is its Value times its formula, from that station's
constants and the variables defined above it. `ipm2json` inlines it: each use becomes `Value * (formula)` (just the
formula when Value is 1), translated in the reading of the row that uses it. The output has no variables, so the
grammar is unchanged.

The guide also has persistent variables, whose values carry from one station to the next: a variable that names itself
(an accumulator such as `d = d + smd`), or one used above its own definition, so that the use sees the previous
station's value. Those depend on the order of the stations, which a weighting function can't, so they're refused.

| Variable | Error |
|----------|-------|
| used in a formula above its definition, or naming itself | `variable:persistent` |
| defined twice | `variable:redefined` |
| with an inclination range | `range` |
| with a unit (any unit but `-`) | `variable:unit` |
| named like an IPM constant or function | `name` |

A variable no source uses is ignored, whatever it is: for example a zero-valued label or an unused accumulator.

## Units

| IPM unit | factor on Value | JSON units |
|----------|-----------------|------------|
| (none, `-`) | 1 | `-` |
| `m` | 1 / 0.3048 | `m` |
| `im`, `i` | 0.3048 | `1/m` |
| `d` | π / 180 | `deg`; `deg/hr` when the source's formulas use `erot` |
| `dnt` | π / 180 | `deg.nT` |
| `nt` | 1 | `nT` |
| `t` | 0.001 | `-`, with the 0.001 in the magnitude |

- Any other unit is refused (`unit:<u>`).
- The magnitude is the first non-zero Value of the source, unsigned, at 12 significant digits when that's within 1e-12
  of it. A row with another Value carries the ratio in its formula, and a negative row carries its sign. A zero row of a
  non-zero source adds nothing, and its field is `0`.
- `ipm2json` writes nothing unless the converted weights equal the IPM's at every diagnostic station (`weights`).
- A depth row's weight is in feet, so its factor includes 0.3048. The numeric check above decides how it lands.

## Vectors

| IPM vector | weighting function field |
|------------|--------------------------|
| `e`, `s` | `depth` |
| `i`, `y` | `inclination` |
| `a`, `x` | `azimuth` (`x` divided by `Sin(Inc)`) |
| `l` | `azimuth`: the lateral formula divided by `Sin(Inc)` |

- `x`/`y` rows give the term `requires: ["xcl_position_direct"]`.
- A source with both depth and angle rows is refused (`mixed_vectors`), and so is one that mixes `x`/`y` with `i`/`a`/`l`.
- An `l` or `x` row is a lateral weight F, defined at a vertical station too. Its azimuth formula F / Sin(Inc) is not, so
  the weighting function also gets the singularity formulas that say the same thing: F along the lateral direction,
  north `-(F) * Sin(AzT)`, east `(F) * Cos(AzT)`, vertical `0` (`propagation.md`, "Vertical stations"). An `a` row gets
  none: where its formula has no value at a vertical station, the engine takes the limit.

## Matching ISCWSA terms

A source becomes a reference to the ISCWSA library term of the same code when all of these hold:

1. its name equals the code, ignoring case;
2. its tie-on is the term's propagation, and the term has no gyro survey mode;
3. its units convert to the term's with the same SI factor;
4. each of its three formulas, after translation, is canonically equal to the library's (`formula.canonical`);
5. its weights equal the library term's at every diagnostic station.

Otherwise it becomes `<ns>:<NAME>` in the vendor library `<ns>:<model>_terms`, which `extends` the ISCWSA library and
holds only the unmatched sources. The log says why a same-named source did not match. When a vendor source's formulas
equal an ISCWSA term under another name, the log says `same_as iscwsa:<CODE>`; the two are never merged.

A matched term takes the library's singularity formulas, which the IPM can't state. Where those differ from the limit of
the IPM's own formula at a vertical station, the converted model follows the library.

## Metadata

`ipm2json` reads these header lines and takes the rest from flags. A flag wins over the header.

| Header | Model field |
|--------|-------------|
| `#ShortName`, `#Description` | `short_name`, `long_name` |
| `#RevisionNumber`, `#RevisionComment` | `revision`, `revision_comment` |
| `#RevisionDate` | `revision_date`, only when written as YYYY-MM-DD (Compass writes day and month in an order the file doesn't state) |
| `#SourceReference`, `#ToolApplication`, `#CurrentStatus` | `source`, `application`, `sheet_status` |
| `#ReplacesTool`, `#RangeComment`, `#Remarks` | `replaces_text`, `range_comment`, `notes` |
| `#InclinationRangeMin`, `#InclinationRangeMax`, `#AzimuthEWRestriction` | `applicability` `inc_min`, `inc_max`, `hor_ew_exclusion` (deg) |

- `--tool-type` and `--author` have no header line. A required field with neither a header line nor a flag stops the run
  (`missing:<field>`); nothing is invented.
- `framework` is `Other` and `status` is `current` unless `--status` is given.
- `origin` is the IPM's file name and the SHA-256 of its bytes.

## JSON to IPM

`json2ipm` writes the header lines above, the column titles, and one row per term per non-zero formula, in model term
order:

- the vector is `e`, `i` or `a`, or `y` and `x` for an `xcl_position_direct` term;
- the tie-on comes from the propagation, and Value is the magnitude;
- the formula is the natural inverse of the table above when its literal reading gives the term's weight, and otherwise
  the literal inverse times its factor.

Singularity formulas aren't written; IPM has no field for them. A matched ISCWSA term gets them back from the library on
the way in. So JSON → IPM → JSON gives the same terms, magnitudes and libraries for every ISCWSA model `json2ipm`
accepts. A vendor term comes back with the same weights, but not always the same text: for example, a `deg/hr` term
whose formulas don't use `erot` returns as `deg` with the 1/3600 in its formula. Two terms whose codes differ only in
namespace or case would be one IPM source, so they are refused (`duplicate_name`). Of the 129 models, 27 are accepted. The rest are refused because they use `XCLTortuosity` (89), gyro survey modes (10) or bias terms (3).
`#ChecksumValue` isn't written.

## Propagation in Compass

Compass treats each interval of a random term independently. SPE 67616, and so a JSON model, shares a station's error
between its two intervals. A converted model therefore gives the same weights as its IPM but not the same random
covariances as Compass: the conversion is of definitions, not of Compass's results.

## Not converted

| Construct | Error |
|-----------|-------|
| a persistent, redefined, ranged or unit-bearing variable, or one named like an IPM constant (see "Variables") | `variable:persistent`, `variable:redefined`, `range`, `variable:unit`, `name` |
| an inclination range | `range` |
| any other function: `SIGN`, `SWON`/`SWOF`, `EXP`, `LN`, `LG`, the inverse and hyperbolic trigonometric functions, `COT`, `FAK` | `function:<NAME>` |
| any other constant: `dog`, `dmd`, `long`, `aze`, `inx` | `constant:<name>` |
| another vector: `b`, `d`, `f`, `j`, `m`, `n` | `vector:<v>` |
| two rows of one vector, or mixed depth and angle rows | `repeated_vector`, `mixed_vectors` |
| rows of one source with different tie-ons | `mixed_tie_on` |
| a unit outside the Units table, or a term needing a capability other than `xcl_position_direct` (`json2ipm`) | `unit:<u>`, `requires:<cap>` |
| a formula the grammar doesn't parse (e.g. implicit multiplication), or a line after the column titles that isn't a full row (fewer than six fields, a vector or tie-on of more than one letter, an empty formula, a Value that isn't a finite number) | `syntax` |
| a tie-on other than `r`, `s`, `w`, `g` | `tie_on:<t>` |
| a source name with `:` (it separates the namespace) | `name` |
| a file that isn't text, or is neither UTF-8 nor cp1252 | `binary`, `encoding` |
| output that doesn't validate, or whose weights differ from the IPM's, or that can't be written (nothing is left behind) | `invalid`, `weights`, `write` |
| two model terms with one IPM name (`json2ipm`) | `duplicate_name` |
| a file without the layout's column titles (Name / Vector / Tie-On / Unit ...) and no row of it; titles with no rows are a tool with no error sources | `no_rows` |
| a gyro model or survey-mode term, a Bias term, a formula variable with no IPM equivalent (`json2ipm`) | `gyro`, `bias`, `variable:<name>` |

Ranges, switches and persistent variables would need a grammar extension; this conversion has none.
