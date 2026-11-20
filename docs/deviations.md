> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Differences from the published sources

ISCWSA's Rev 5.1 diagnostics (iscwsa.net file 806, the [conformance vectors](conformance.md)) are normative. In a few
places the published text (the ISCWSA MWD workbook, iscwsa.net file 809; the Rev 5.13 definition; SPE 67616; SPE 90408;
the XCL Supplement r16) disagrees with the diagnostics, contradicts itself, or leaves a choice open. This page lists every
place where this repository, or the engine used to check it, departs from the published text, and why.

Scope: every library, `iscwsa:rev0`, `rev1`, `rev2`, `rev3`, `rev4`, `rev5`, `iscwsa:rot6axis` and `iscwsa:spe90408`, and the 129 models and six SPE 90408 example models built on them.

The status of every item is **provisional, pending sub-committee review**.

There are two kinds of item:

- **Errata** change the formula text in a library. Each erratum is recorded in `tools/errata.json`, and the library entry
  carries it in its `errata` array (`sheet_text`, `corrected`, `source`, `reason`, `status`). The validator reports
  proposed errata as `ERRATA_PROPOSED` warnings, and `--release` turns them into errors.
- **Conventions** leave the formula text unchanged. They govern how an engine evaluates or propagates the formulas. Some
  of them cannot be expressed in the JSON yet: an engine has to apply them by itself to reproduce 806. [`propagation.md`](propagation.md) describes them,
  each with its row here.

The check: an independent engine built only from published sources (not part of this repository; it reads the JSON with `tools/formula.py`; no Well Architect, Compass or welleng
code) reproduces all 19,476 station/term checks of 806 with the items below. The "without it" counts are the stations
that fail when only that item is reverted, under the tolerance below (measured 2026-10-20).

The same engine, reading the JSON files alone, reproduces 60 of 60 printed values of SPE 67616 Table 3 (cases 1 to 7, the 6 bias values
included) and 491 of 492 printed values of SPE 90408 Appendix E (the exception is C14). In rows C13 to C23 and C27 to C29 the
"without it" count is the number of printed values that fail under the rejected reading. C24 to C26 and C30 are not measured.

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
| C11 | `Bias` propagation | New propagation value `Bias` (`B`, P flags 0, 0, 0) for DSTB and AMIB on the `iscwsa:rev0`, `rev1` and `rev2` bias sheets (ISCWSA MWD bias Rev0/1/2). The terms carry `requires: ["bias_terms"]`: an engine without survey bias refuses them | SPE 67616 Appendix A (Eqs. A-17 to A-19) and Table 3 cases 5 and 6; the sheets say "Use of Bias Models Not Recommended" | Table 3 cases 5 and 6 (`iscwsa:MWD_bias_Rev0`): the reference engine reproduces all 18 printed values, the 6 bias values among them | yes: propagation `Bias` and the per-term `requires` |
| C12 | Sheet data gap: `XCLTortuosity` | None: nothing is invented. Five models use XCLA/XCLH but their sheets give no `XCLTortuosity` parameter (`generic_iscwsa:A027Ub`, `A028Ub` and their `_Fl` variants, and `iscwsa:D007Ma`), so engines refuse them | the sheets (files 807, 808, 1052) | not measured (no published diagnostic); 5 models refused | n/a (data missing from the sheets) |
| C13 | SPE 90408 Table 10 depth systematic reference | The Appendix E vectors declare `inputs.vertical_reference` (0.5 m). A calculation adds its square, 0.25 m², to VV at every station. It is not a model term: it has no depth, inclination or azimuth weight. Calculations given no such input add nothing | SPE 90408 Table 10: "virtually a TVD reference error ... independent of well bore direction" | 25 of 492 printed values fail without it (24 in the feet well 2, where 0.25 m² is 2.69 ft², over the paper's 2 units; and the known miss, C14); 1 fails with it | yes: `inputs.vertical_reference` in `conformance/vectors/spe90408/appendix_e.json` |
| C14 | Known miss: example model #1, well 3, 3000 m, NN | None. It is listed in the vector file's `known_misses`, with its reason: not established; a station-list difference is likely, since the paper gives no station list. The calculation gives 123.0 against the printed 118 (limit 2) | SPE 90408 Table E3 | 1 of 492 printed values fails with every convention applied | yes: `known_misses` |
| C15 | Gyro mode boundaries | A station at a boundary belongs to the range that starts there (start <= Inc < end); the highest range includes its end | SPE 90408 Table 11 note 1 ("a logical unbroken sequence with no overlap zones"). No printed value tells the two readings apart | 0 fail with the other reading (start < Inc <= end): it gives the same 336 results, so the text's reading is untested | yes: `start_inc`, `end_inc` as published; the edge rule is the engine's |
| C16 | Gyro initialisation point | With `init_inc` >= 0 the initialisation steps back to the station where Inc is not above `init_inc` (Fig. C1 box 6). A negative `init_inc` initialises at the first survey station | SPE 90408 Fig. C1; Table 11 note 2 | 7 fail if it initialises at the current station (example model #3) | **no** |
| C17 | Initialisation inclination (box 7) | `init_inc` itself when the step back reached a station at or below it; the station's own inclination only when it stopped at the first station still above `init_inc` | SPE 90408 Fig. C1 box 7. The printed chart can also be read as "the station's inclination whenever it is below `init_inc`" | 4 fail with that reading (example model #3, `init_inc` 17°, initialised at 15.8° on well 1) | **no** |
| C18 | Keeping an initialisation (box 11) | Keep it unless Inc <= `init_inc` and MD >= the last initialisation depth plus `min_distance` | SPE 90408 Fig. C1 box 11 and Table 11 ("minimum distance between initializations"). The box prints "IF ((I(i) > init_inc) AND (D(i) < init_D + min_D))" for keeping | 63 fail if the box is read as printed (re-initialise at every station at or below `init_inc`; example models #2 and #4, whose `init_inc` is 0° and 3°, through the vertical top hole) | **no** |
| C19 | Random walk after a re-initialisation | A new walk, independent of the earlier one. The drift stays one systematic source | SPE 90408 Tables 6-8 give both as mode S within a run | 7 fail with one walk across the re-initialisation (example model #4, well 3 after 2520 m) | **no** |
| C20 | Continuous term at the initialisation station | h is 0 there and accumulates from the next interval | SPE 90408 Fig. C1 box 9 ("preserving from last initialisation") | 7 fail if the interval ending at the initialisation station is counted | **no** |
| C21 | Stations between the initialisation point and the current station | They keep their own, stationary result | SPE 90408 Fig. C1 boxes 13-16 describe redoing them | 0 fail if they are redone: no printed value changes by more than 0.1 | **no** |
| C22 | Azimuth of a vertical initialisation station | The held stationary terms use the stored azimuth of the vertical station the step back reached | SPE 90408 Appendix E example model #4, well 3 (stepped back to the vertical station at 2850 m) | 5 fail if the arc's leaving azimuth (the next non-vertical station's) is used, and the same 5 if the azimuth is interpolated linearly at `init_inc` between the stations either side | **no** |
| C23 | Model with continuous terms and no stationary range | There is no stationary section. The stationary terms apply only at an initialisation | SPE 90408 Tables D4 and D5 (example models #4 and #5 have no stationary mode) | 80 fail with a stationary range of 0-180°, the sheets' default (46 in #4, 34 in #5). With a stationary range of 0 to `init_inc`, 30 fail in #4 and 0 in #5 | yes: no `stationary` block |
| C24 | Initialisation inclination of a stationary block | The stationary block's `init_inc` is kept as published but not used. The engine takes one `init_inc` per run, from the continuous blocks, which must agree (`GYRO_INIT_MISMATCH`) | No sheet's stationary-only model initialises anything. Example models #4 and #5 have no stationary block | n/a: not measured (no published value depends on it) | yes: carried as published |
| C25 | Names of the SPE 90408 library terms | `iscwsa:spe90408` carries only the Table 1-4, 6 and 8 rows that no sheet carries. Its term names (for example `GXYZ-B1`, `AXY-SF`) are provisional, in the Rev 5 style, for the sub-committee to settle | SPE 90408 Tables 1-4, 6 and 8, each term's `source` | n/a: a naming choice | yes: the library |
| C26 | SPE 67616 tolerance | `hla` vectors: each sigma and bias within `max(0.005 * abs(ref), 0.002)`, each correlation within 0.01. Provisional; see [`conformance.md`](conformance.md) rule 3 | The print step of the paper's sigmas (0.002) and correlations | n/a: not derived from the data. The printed values of Table 3 agree with the calculation to the last digit when C28 is applied | yes: stated in `conformance.md` |
| C27 | Survey legs | A station uses its own leg's magnitudes. The interval between two legs gets one half from each. Random terms are independent at every station; systematic terms sum within a leg, and legs are independent; well and global terms are one sum across legs. A term name is one source in every leg that has it, and a name with two propagation modes in two legs is refused. A leg boundary is not a tie-on | SPE 67616 Appendix A and its statement that r1, r2 and r3 "should be the same for all survey legs"; example 7 | 9 of 36 printed Table 3 values fail if example 7 is run as one leg of either model | yes: the case's `legs` list in `table3.json` |
| C28 | SPE 67616 Table 3 tie-on | Zero uncertainty at the tie line: the slot is no error source and no interval is doubled | SPE 67616 Table 3 caption: "uncertainty at the tie line (MD = 0) is zero" | 1 of 36 printed values fails with the 806 rule (C5) | yes: `inputs.tie_on` in `table3.json` |
| C29 | Bias term weighting | A bias term (`AMIB`, `DSTB`) has the weighting function of the term it models (AMID, DST) and adds no covariance; its σ is a separate symmetric term (AMID 0.5°) or 0 (DST). Table 3's bias option is Table 4's footnotes, term for term the `iscwsa:MWD_bias_Rev0` sheet | SPE 67616 Table 4 footnotes ("When modeled as bias: μ = 0.33°, σ = 0.5°"; "μ = 4.4e-7 m^-1, σ = 0") and Eqs. A-17 to A-19 | 11 of 18 printed values of cases 5 and 6 fail if the biases are added to the basic model (AMID 0.6° and DST 2.2e-7 m^-1 kept) | yes: the model's terms |
| C30 | Relative uncertainty between wells | A global term name in both wells is one error source, fully correlated (Eq. A-24); a name in one well only, and every other mode, is independent between the wells. Open reading | SPE 67616 Eqs. A-14, A-24, A-25 | not measured (no published two-well result) | no |

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

