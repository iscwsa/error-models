> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Differences from the published sources

ISCWSA's Rev 5.1 diagnostics (iscwsa.net file 806, the [conformance vectors](conformance.md)) are normative. In a few
places the published text (the ISCWSA MWD workbook, iscwsa.net file 809; the Rev 5.13 definition; SPE 67616; SPE 90408;
the XCL Supplement r16) disagrees with the diagnostics, contradicts itself, or leaves a choice open. This page lists every
place where this repository, or the engine used to check it, departs from the published text, and why.

Scope: every library, `iscwsa:rev0`, `rev1`, `rev2`, `rev3`, `rev4`, `rev5` and `iscwsa:rot6axis`, and the 129 models built on them.

The status of every item is **provisional, pending sub-committee review**.

There are two kinds of item:

- **Errata** change the formula text in a library. Each erratum is recorded in `tools/errata.json`, and the library entry
  carries it in its `errata` array (`sheet_text`, `corrected`, `source`, `reason`, `status`). The validator reports
  proposed errata as `ERRATA_PROPOSED` warnings, and `--release` turns them into errors.
- **Conventions** leave the formula text unchanged. They govern how an engine evaluates or propagates the formulas. Some
  of them cannot be expressed in the JSON yet: an engine has to apply them by itself to reproduce 806. They will be
  specified in `docs/propagation.md` (planned).

The check: the private independent engine (reads the JSON with `tools/formula.py`; no Well Architect, Compass or welleng
code) reproduces all 19,476 station/term checks of 806 with the items below. The "without it" counts are the stations
that fail when only that item is reverted, under the tolerance below (measured 2026-10-20).

## Errata (libraries `iscwsa:rev5` and `iscwsa:rot6axis` only)

| # | Entry | Sheet text (file 809) | Library text | Basis | Without it |
|---|---|---|---|---|---|
| E1 | XYM3E inclination | `Cos(Inc) * Cos(AzT) * Max(1, sqrt(10/(MD-MDPrev)))` | `Abs(Cos(Inc)) * …` | 806; Rev 5.13 §5.1.2 table (p. 31) prints `Abs(Cos(I))` | 378 XYM3E stations fail, and 162 TOTAL (E1-E6 reverted together) |
| E2 | XYM3E azimuth | `(Cos(Inc) * Sin(AzT) / Sin(Inc)) * …` | `-(Abs(Cos(Inc)) * Sin(AzT) / Sin(Inc)) * …` | as E1; the sign is also opposite in the sheet | (with E1) |
| E3 | XYM4E inclination | `Cos(Inc) * Sin(AzT) * …` | `Abs(Cos(Inc)) * …` | consistency with E1 and Rev 5.13 §5.1.2 | none: 806 does not exercise it |
| E4 | XYM4E azimuth | `(Cos(Inc) * Cos(AzT) / Sin(Inc)) * …` | `(Abs(Cos(Inc)) * …` | as E3 | none |
| E5, E6 | XCLA `singularity_north`, `singularity_east` | `XCLTortuosity * RAD * (MD - MDPrev)` | `XCLTortuosity * (MD - MDPrev)` | the sheet's own XCLA/XCLH main formulas use XCLTortuosity in rad/m; the singularity text treats it as deg/m | none: engines need not evaluate these (C3) |

Notes:

- `iscwsa:rot6axis` (the RCS candidate sheet, file 1052) carries the same sheet text for E1-E6 (apart from spacing and
  `Sqrt` against `sqrt`), so it has the same six errata, with the same corrected text, source and reason, all proposed. They are carried to `rot6axis` because its sheet text is identical; no 806 count exists for it, since 806 exercises `rev5` only.
  The other libraries (`rev0`-`rev4`) have none of these weighting functions.
- SPE 90408 (Table 9 and Appendix B, Alternative 3) gives the misalignment weight as `cos I`, **without** the absolute
  value. It differs from the Rev 5.13 definition only for inclinations above 90°. The 806 well 3 reaches 110° and passes
  with `Abs`, so the diagnostics follow the Rev 5.13 form.
- Even with E5/E6 applied, the XCLA singularity text is not the limit of the XCLA azimuth formula as the inclination
  goes to 0. The two agree only at an azimuth of 0. Engines should use the limit (C3).

## Conventions (formula text unchanged)

| # | Topic | What the engine does | Basis | Without it | In the JSON? |
|---|---|---|---|---|---|
| C1 | XCLA / XCLH propagation | Position-direct: the error tilts only the interval ending at the station, by its full course length ΔMD, with no forward coupling | XCL Supplement r16; Rev 5.13 eqs 40-41; the sheet comment "Tangential Calculation" | 538 XCLA and 538 XCLH stations fail (ordinary weighting-function propagation at 0.167) | yes: the library's `requires: ["xcl_position_direct"]` |
| C2 | XCLA after a vertical station | A vertical station (Inc 0) has no azimuth, so `AzT - AzPrev` from it is 0 | not published; found from 806 (well 1, MD 1230: Inc 0→2°, Az 0→75°) | 269 XCLA stations fail | **no** |
| C3 | Vertical stations | Where a weight has `1/Sin(Inc)`, the engine multiplies by the `sin I` of the position derivative and takes the finite limit numerically. It uses the singularity formulas only where that limit does not converge (`Tan(Pi/2 - Inc)` in ABXY-TI2/ABIXY-TI2) | Rev 5.13 §4.6 and §11.5: the singularity formulas "may be substituted when vertical" | n/a (some limit is required) | partly: the singularity formulas are carried verbatim; the choice of limit is the engine's |
| C4 | `Az` in singularity formulas and the Rev0-2 sensor terms | Decided: `Az` is the station's recorded azimuth (true), `AzT`. The variable is kept verbatim in the formula text | 806 (ABXY-TI2S): `az=AzT` passes 541 of 541 stations; `az=AzM` passes 125 of 541. Rev 5.13 §11.5 writes the ABXY-TI2 vertical row with `Am` (magnetic) and the RCS sheet (`iscwsa:rot6axis`) writes `AzM` in ABXY-TI2: both are listed for the sub-committee (C9). The Rev0-2 sensor terms (`Az + TF`) and CNA follow the same reading; no published diagnostic exercises them | with `Az` = `AzM`, 416 of 541 ABXY-TI2S stations fail (125 pass). Rev0-2 sensor terms and CNA: not measured (no published diagnostic) | the variable is kept verbatim (`docs/grammar.md`); its meaning is documented there |
| C5 | First station after the tie-on (slot) | XYM3E/XYM4E: the slot is not a separate error source, and the first interval's derivative is counted twice at station 1. Other terms: the slot is an ordinary SPE 67616 error source. The two rules give the same 806 results for every other Rev 5 term | 806; SPE 67616 for the other terms. Under SPE 67616 the XYM3E weight at the slot is undefined (`Sqrt(10 / 0)`) | 538 XYM3E and 538 XYM4E stations fail | **no** |
| C6 | `XCLTortuosity` unit | The formulas take it in rad/m. The model parameter stays as published (`1 deg/100ft`), and the engine converts it | the XCLA/XCLH main text compares it with radians (`docs/grammar.md`) | taking it as deg/m (the singularity text's reading): 538 XCLA and 538 XCLH stations fail | yes: the parameter's `unit` |
| C7 | Station input and azimuth reference | Stations are the printed 806 values (Inc/Az to 2 decimals), taken as true azimuths (grid convergence 0); toolface 0 | 806 header and station table | n/a | n/a (test-well data) |
| C8 | DSTG magnitude | 2.5e-7 1/m from the sheet. The 806 term table prints `0.000000` (6 decimals), but its covariances use 2.5e-7 | file 809 | at 0, 517 DSTG stations fail | yes: model magnitude |
| C9 | RCS ABXY-TI2 uses `AzM` | None: the library carries the RCS sheet text unchanged (`AzM` in ABXY-TI2 `azimuth`, `singularity_north`, `singularity_east`). It is not corrected to `Az`, because there is no published diagnostic for the RCS model | file 1052 (`iscwsa:rot6axis`), against Rev 5.13 §11.5 (`Am`) and the Rev 5 sheet (`Az`, C4); the sheet text stays as published | not measured (no published diagnostic) | yes: carried verbatim; sub-committee to say which azimuth the RCS formula means |
| C10 | `hor_ew_exclusion` geometry | A station is outside a model's applicability when `abs(sin(Inc) * sin(AzM)) > cos(hor_ew_exclusion)` (the wellbore is within the exclusion angle of horizontal magnetic east-west), or when `Inc < inc_min` or `Inc > inc_max` | no published definition; the singular denominator `1 - sin²I * sin²AzM` vanishes exactly on that line. In the engine self-check, 44 models exclude 108 stations of wells 1-3 (433 checked) and 67 models check all 541 | not measured (no published diagnostic); a different reading would change which stations the self-check skips | yes: `applicability` carries the three limits; the geometry is the engine's |
| C11 | `Bias` propagation | New propagation value `Bias` (`B`, P flags 0, 0, 0) for DSTB and AMIB on the `iscwsa:rev0`, `rev1` and `rev2` bias sheets (ISCWSA MWD bias Rev0/1/2). The terms carry `requires: ["bias_terms"]`, and engines refuse them until bias propagation is specified (Plan 3) | SPE 67616 bias terms; the sheets say "Use of Bias Models Not Recommended" | not measured (no published diagnostic); the 3 bias models are refused | yes: propagation `Bias` and the per-term `requires` |
| C12 | Sheet data gap: `XCLTortuosity` | None: nothing is invented. Five models use XCLA/XCLH but their sheets give no `XCLTortuosity` parameter (`generic_iscwsa:A027Ub`, `A028Ub` and their `_Fl` variants, and `iscwsa:D007Ma`), so engines refuse them | the sheets (files 807, 808, 1052) | not measured (no published diagnostic); 5 models refused | n/a (data missing from the sheets) |

## Tolerance

The tolerance is set in [`conformance.md`](conformance.md) rule 3, at each station and term:
`max|calc - ref| <= max(0.001 * max|ref|, 1e-4)` m².

- **The floor (1e-4 m²)** is two half-steps of the 4-decimal print of the covariances.
- **The relative part (0.1%)** allows for the 2-decimal print of the station inclination and azimuth. On 806 the engine's
  worst relative difference, at stations whose difference exceeds the floor, is 0.05% (XYM3E/XYM4E, well 2, around MD
  2,900-3,750 m). The 0.1% bound is twice that.
- A pure absolute rule of 5e-5 m² fails 244 checks, because of print rounding alone.
- Before this page was written the relative part was 1%. That value was chosen to match the engine's other suites and
  was not derived from the data.

