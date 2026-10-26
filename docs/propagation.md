> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Propagation

How an engine turns a model's formulas into a position covariance. This page is **informative**. The [conformance
vectors](conformance.md) are normative: where this page and a vector disagree, the vector wins.

Each rule names its published basis: SPE 67616, SPE 90408 (a table, figure or note), the ISCWSA sheets, or ISCWSA's Rev
5.1 diagnostics (iscwsa.net file 806). A rule that the published text leaves open, and that the printed numbers decided,
is labelled in bold with the row of [`deviations.md`](deviations.md) that counts the printed values failing under the
rejected reading, for example **Convention C16**. A rule the printed values do not decide is labelled **Open reading** and still has a row. Everything on this page is provisional, pending sub-committee review.

## The position derivative

A model gives, for each error source, a weight for the depth, inclination and azimuth of a station (the weighting
function) and a magnitude. SPE 67616 Appendix A turns these into a position error with the balanced-tangential
(average-angle) form of the survey calculation.

- Between stations 1 and 2, with t = (sin I cos A, sin I sin A, cos I) and ΔMD = MD2 - MD1, the displacement is
  Δr = ΔMD / 2 · (t1 + t2).
- The derivative of Δr with respect to the depth, inclination and azimuth of a station is dr/dp. It is ½ (t1 + t2) for the
  depth of station 2 (the opposite sign for station 1), and ΔMD / 2 · ∂t/∂I and ΔMD / 2 · ∂t/∂A for the angles. ∂t/∂A
  carries a factor sin I.
- For a source with magnitude σ and weight w at station k, the vector error is e_k = σ (dr_k/dp_k + dr_k+1/dp_k) · w_k:
  the interval before the station and the interval after it, each with the weight and magnitude of station k's own leg
  (SPE 67616 Appendix A). At the station of interest there is no interval after it, so only the interval
  ending there counts.
- The covariance is a sum of the outer products of these vectors. The next section says which ones are summed first.

## Random, systematic, well and global terms

SPE 67616 Appendix A gives each error source a propagation mode.

- **Within a leg.** Random (R): every station's error is independent, so the outer products are summed.
  Systematic (S): the vector errors are summed along the leg first and the outer product is taken once, so the error is
  fully correlated along the leg. The tie-on source e* is added to the sum (next section).
- **Across wells.** Well-by-well (W) is correlated along a well and independent between wells. Global (G) is correlated
  along every well and between wells. For one well, S, W and G give the same result. Only well-by-well and
  global terms couple two wells.
- **Across legs.** A leg is a contiguous set of stations surveyed with one tool (SPE 67616, introduction). Random terms stay
  independent at every station. Systematic terms sum within a leg, and different legs are independent. Well-by-well and
  global terms are one sum across all legs. SPE 67616 says r1, r2 and r3, the properties of an error source, "should be the
  same for all survey legs".
  - **Convention C27.** A term name is one error source in every leg that has it (for example the declination in both
    models of example 7). An engine refuses a model list where one name has two propagation modes in two legs. The
    interval between the last station of one leg and the first of the next gets one half from each leg's model, and a leg
    boundary is not a tie-on: no interval is doubled there. The paper's example 7 (well 3 in three legs, "included as a test
    of error term propagation") fixes it.

## The tie-on

The tie-on is the first station of the well, at MD 0 (the "slot").

- SPE 67616 Table 3 says "uncertainty at the tie line (MD = 0) is zero".
  - **Convention C28.** The `hla` vectors set `tie_on: zero_uncertainty`: the slot is no error source, and the first
    interval is not doubled.
- The ISCWSA diagnostics (file 806) differ.
  - **Convention C5.** For XYM3E and XYM4E the slot is not a separate source and the first interval's inclination and
    azimuth derivative is counted twice at station 1. For every other term the slot is an ordinary SPE 67616 error source:
    its error is the derivative of the first interval with respect to the slot's own attitude, carried into every later
    station. For a systematic term the two rules agree, so 806 cannot tell them apart.
  - Under SPE 67616 the XYM3E weight at the slot is undefined (`Sqrt(10 / 0)`).
- The JSON cannot express the choice between these. An engine takes it from the vector's `inputs`.

## Vertical stations

At a vertical station (Inc 0) the azimuth is undefined and some weights have a `1/Sin(Inc)` factor.

- **Numeric limit.** The azimuth column of dr/dp carries `sin I`, so a weight `w/Sin(Inc)` times that column is finite. An
  engine multiplies by the `sin I` analytically and takes the finite limit, which covers every station of every ISCWSA
  test well. It uses the published singularity formulas only where the limit does not converge: `Tan(Pi/2 - Inc)` in
  ABXY-TI2 and ABIXY-TI2 (Rev 5.13 §4.6 and §11.5, which say the singularity formulas "may be substituted when
  vertical"). See C3 in `deviations.md`. The formulas themselves are carried verbatim in the libraries (`singularity_north`,
  `singularity_east`, `singularity_vertical`). `Az` in them is `AzT` (C4).
- **XCLA after a vertical station.**
  - **Convention C2.** A vertical station has no azimuth, so `AzT - AzPrev` from it is 0. File 806 shows it (well 1, MD
    1230: Inc 0 to 2°, Az 0 to 75°).
- **Open.**
  - The XCLA singularity text is not the limit of the XCLA azimuth formula at an inclination of 0 unless AzT is 0. The
    text, with its two proposed errata (E5 and E6), is listed in `deviations.md`. Engines should use the limit.
  - A weight `1/Cos(Inc)` (the xy gyro terms GXY-B1, GXY-G4 and GXY-RN) evaluated from its JSON text at
    exactly Inc 90° gives a very large finite number (about 1e16 in floating point), not an undefined value. SPE 90408
    prints "-" for the Example Models #1 and #2 at 90° and above, and the sheets give an inclination limit of 89°, which
    #1 and #2 use (`inc_max`: a station above it is outside the applicability). An engine should treat the term as
    undefined from 90°. No vector station is at exactly 90°.
  - The same applies to the z-gyro accumulator, whose weight is `1/Cos(Im)`, at an interval mean inclination of exactly
    90°. Example Model #2 is therefore limited to 89° (`inc_max`), as #1 is.

## Toolface of the Rev0-2 sensor terms

The Rev0-2 sensor terms (ABX to MSIY, MX, MY) depend on the toolface, which the 806 diagnostics do not give: their TF
column is 0 and their model is toolface-independent.

- SPE 67616 Appendix B gives the toolface from successive surveys (eqs B-1 to B-5). The `hla` vectors say
  `toolface: borehole`.
- Open: no published diagnostic exercises the term at an inclination where the toolface matters, so the value at the first
  station has no published basis and no count.

## Position-direct XCLA and XCLH

The XCLA and XCLH rows are marked "Tangential Calculation" in the sheet.

- **Convention C1.** The error tilts only the interval ending at the station, by its full course length ΔMD (not half), and
  has no effect on the next interval. The library's `requires: ["xcl_position_direct"]` carries this. Basis: XCL Supplement
  r16; Rev 5.13 eqs 40-41.
- The weight at the slot has zero course length, so the slot adds nothing to them.
- `XCLTortuosity` is taken in rad/m, whatever the parameter's `unit` (`docs/grammar.md`; C6 in `deviations.md`).

## Gyro survey modes

A model with a `gyro` block (10 of the sheets' models, and the SPE 90408 example models) switches between survey modes by
inclination. The terms that need this declare `gyro_modes`. The model is SPE 90408 Appendix C, Fig. C1 (the generalised
gyro model), with the continuous equations 5a to 6c and Tables 6 to 8, and Table 11 for the parameters. The checks are
SPE 90408 Appendix E, Example Models #2 to #5 (continuous) and #1 and #6 (stationary).

- **Modes and ranges.** The stationary range and each continuous range are `start_inc` to `end_inc` blocks of the `gyro`
  object. Table 11 note 1 says they are "a logical unbroken sequence with no overlap zones": the validator rejects overlap or
  reversed ranges (`GYRO_RANGE`). Two continuous blocks with the same axes are rejected (`GYRO_AXES_DUPLICATE`), and so is a
  model with a continuous block but no `min_distance` (`GYRO_MIN_DISTANCE_MISSING`). Two continuous blocks with the same axes are rejected (`GYRO_AXES_DUPLICATE`), and so is a
  model with a continuous block but no `min_distance` (`GYRO_MIN_DISTANCE_MISSING`).
  - **Open reading, not decided by the printed values (C15).** A station at a boundary belongs to the range that starts there (start <= Inc < end), and the highest
    range includes its end.
  - A station above every range is in no mode. Every gyro term is undefined there, and an engine excludes the station.
- **Terms.** Tables 3, 4 and 5 (the stationary gyro terms and the external reference) are stationary terms held at an
  initialisation. Tables 6, 7 and 8 (drift and random walk) are continuous terms. A continuous term's gyro axes (xy, z, xyz)
  and kind come from the accumulator its azimuth formula names (`grammar.md`). It needs a continuous block with those axes,
  and an engine refuses the model without one (`GYRO_AXES_MISSING`).
- **Accumulation.** Over an interval, with ΔMD, running speed c and mean inclination Im, drift is h = hPrev + g ΔMD / c and
  random walk is h = sqrt(hPrev² + g² ΔMD / c). g is 1 (xyz), `1/Sin(Im)` (xy) or `1/Cos(Im)` (z). Only the mode in use
  accumulates. Another continuous mode keeps its value (Fig. C1 box 12). In stationary mode the continuous terms are 0. The
  paper's text gives these.
- **Initialisation.** A continuous mode begins at an initialisation, in Fig. C1 boxes 6 to 11.
  - **Convention C16.** With `init_inc` ≥ 0, the initialisation steps back to the station where the inclination is not
    above `init_inc` (box 6). It does not initialise at the current station. A negative `init_inc` (the sheet's `-1
    [Initialised at Surface]`) initialises at the first survey station (Table 11 note 2).
  - **Convention C17.** The initialisation inclination of box 7 is `init_inc` itself when the step back reached a station at
    or below it, and the station's own inclination only when it stopped at the first station still above `init_inc`.
  - **Convention C18.** Box 11 keeps the initialisation unless Inc <= `init_inc` and MD >= the last initialisation depth
    plus `min_distance` ("minimum distance between initializations"). The printed box reads the other way round, which
    re-initialises at every station at or below `init_inc` and leaves `min_distance` with no effect.
  - **Convention C22.** When the step back reaches a vertical station, the held terms use that station's stored azimuth.
    The azimuth the arc leaves it in, and the azimuth interpolated at `init_inc` between the stations either side, are
    rejected.
- **Held terms.** The stationary terms are evaluated once, at the initialisation inclination and the azimuth of the
  initialisation station, with the noise reduction factor, and hold for every later continuous station (box 9, "preserving
  from last initialisation"). A random one becomes systematic from there on, as a new source for each initialisation: SPE
  90408, "random errors shall be propagated systematic (S) throughout the subsequent continuous azimuth measurements". The
  continuous terms restart from 0 (box 9).
- **After an initialisation.**
  - **Convention C19.** A random walk after a re-initialisation is a new walk, independent of the earlier one. The drift
    stays one systematic source.
  - **Convention C20.** The continuous terms are 0 at the initialisation station and accumulate from the next interval.
  - **Open reading, not decided by the printed values (C21).** The stations between the initialisation point and the current station keep their own, stationary
    result. Redoing them with the initialisation (boxes 13 to 16) changes no printed value by more than 0.1, so the simpler
    reading is used.
- **No stationary range.**
  - **Convention C23.** A model with continuous terms and neither `start_inc` nor `end_inc` for a stationary mode has no
    stationary section. Its stationary terms apply only at an initialisation. Basis: Example Models #4 and #5 have none.
- **`NoiseReductionFactor`.** 1 in stationary mode. At an initialisation it is the model's `init_factor` (1 if none). SPE 90408
  Tables 3 and 4, note 3: "f = 1 for stationary mode, f < 1 for continuous initialisation".
- **`IncCant`.** The inclination seen by a canted xy accelerometer, `Inc - k * Cant`, with k = -1 when the tool is turned 180°
  above 90° (`cant_switching`) and k = 1 otherwise (SPE 90408 Table 2). With no cant it is `Inc`.
- **Inclination of 90° and beyond.** The xy gyro terms with `1/Cos(Inc)` or `Tan(Inc)` have no value from 90° on: the
  sheets' range comment ("Tool model fails at 90 deg inclination") and SPE 90408 Tables E1-E3, which print "-". The
  covariance of every later station is also undefined, because the sums include it.
- **Vertical reference.** SPE 90408 Table 10's depth systematic reference (0.5 m) is "virtually a TVD reference error ...
  independent of well bore direction", so it has no depth, inclination or azimuth weight and is not a model term.
  - **Convention C13.** The Appendix E vector declares it as `inputs.vertical_reference`, and an engine adds its square to
    VV at every station.

## Bias terms

SPE 67616 Table 3 is the no-bias option, and nothing published defines how a bias term moves the expected position. The
terms `DSTB` and `AMIB` carry propagation `Bias` and `requires: ["bias_terms"]`, and engines refuse a model that uses them
(C11 in `deviations.md`). Three models are refused for this reason.
