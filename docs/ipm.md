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
- **Functions** `SIN COS TAN ABS SQRT SQR MAX MIN` (`SQR` is the square root, as in the guide's formulas).
- **Operators** `+ - * / ^`, and the constants below.

## Constants

IPM formulas work in radians and feet. Each formula has two readings:

- **literal**: the IPM meaning exactly, with lengths in feet;
- **natural**: lengths in metres (`mtf` is 1), as the ISCWSA library writes its formulas.

| IPM | literal | natural |
|-----|---------|---------|
| `inc`, `azt`, `azm`, `dip`, `lat`, `tfo` | `Inc`, `AzT`, `AzM`, `Dip`, `Lat`, `TF` | the same |
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
- `daz` assumes an azimuth change under 180°, as the XCL sheets do.
- `erot`: the guide's Earth rate is 15.041 deg/hr; `EarthRate` is SPE 90408's 7.2921159e-5 rad/s (15.0411 deg/hr). A
  converted formula with `erot` therefore differs from Compass's by 5e-6 relative.

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
- The magnitude is the first row's Value, unsigned. A row with another Value, or a negative one, carries the ratio in its
  formula.
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
- No singularity formula is written for an `l` row. At a vertical station the azimuth weight is taken as its limit, as
  for the library terms (`propagation.md`, "Vertical stations").

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
the way in, so JSON → IPM → JSON gives the same model for every model `json2ipm` accepts. Of the 129 models, 27 are
accepted. The rest are refused because they use `XCLTortuosity` (89), gyro survey modes (10) or bias terms (3).
`#ChecksumValue` isn't written.

## Propagation in Compass

Compass treats each interval of a random term independently. SPE 67616, and so a JSON model, shares a station's error
between its two intervals. A converted model therefore gives the same weights as its IPM but not the same random
covariances as Compass: the conversion is of definitions, not of Compass's results.

## Not converted

| Construct | Error |
|-----------|-------|
| a variable row (Vector or Tie-on `n`), or a formula naming one | `variable` |
| an inclination range | `range` |
| any other function: `SIGN`, `SWON`/`SWOF`, `EXP`, `LN`, `LG`, the inverse and hyperbolic trigonometric functions, `COT`, `FAK` | `function:<NAME>` |
| any other constant: `dog`, `dmd`, `azi`, `long` | `constant:<name>` |
| another vector: `b`, `d`, `f`, `j`, `m`, `n` | `vector:<v>` |
| two rows of one vector, or mixed depth and angle rows | `repeated_vector`, `mixed_vectors` |
| rows of one source with different tie-ons | `mixed_tie_on` |
| a unit outside the Units table, or a term needing a capability other than `xcl_position_direct` (`json2ipm`) | `unit:<u>`, `requires:<cap>` |
| a formula the grammar doesn't parse (e.g. implicit multiplication) | `syntax` |
| a gyro model or survey-mode term, a Bias term, a formula variable with no IPM equivalent (`json2ipm`) | `gyro`, `bias`, `variable:<name>` |

Variables, ranges and switches would need a grammar extension; this conversion has none.
