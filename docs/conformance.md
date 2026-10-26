> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Conformance

Conformance vectors let an implementation check that it evaluates a model the way the ISCWSA intends.

## Vectors

- Vectors come only from published results. Each manifest entry has a `kind`, which says what the file holds and how it is
  checked. Three kinds exist.
- `per_term_nev`: ISCWSA's "ErrorModelDiagnostics Rev5-1" (iscwsa.net file 806) for ISCWSA test wells 1-3, in
  `conformance/vectors/iscwsa_rev5-1/`.
  - The files are ISCWSA's own published output, unchanged (byte-for-byte; sha256 values are in that directory's `README.md`).
  - Each file gives the well reference parameters, the compiled error sources, and, per survey station, the covariance
    (NN, EE, VV, NE, NV, EV in m^2) contributed by each term plus a `TOTAL` row.
- `total_nev`: SPE 90408 Appendix E, Tables E1-E3 (`conformance/vectors/spe90408/appendix_e.json`). For each of the example
  models `iscwsa:SPE90408_Ex1` to `Ex6` and each of test wells 1-3, the printed total position covariance
  `[NN, NE, NV, EE, EV, VV]` at the printed depths. Units are m^2, and ft^2 with depths in ft for well 2, as printed.
  - The `inputs` say that azimuths are UTM grid azimuths and give each well's longitude and UTM zone. The first-order grid
    convergence is `(lon - (6 * zone - 183)) * sin(lat)` degrees.
  - Station lists are those of the ISCWSA test wells that the `per_term_nev` files use; they are not repeated.
- `hla`: SPE 67616 Table 3 (`conformance/vectors/spe67616/table3.json`), cases 1, 2, 3 and 7. Each case names the well and
  its survey legs (`model` and the last MD of the leg, in the well's unit, so feet for well 2) and prints, at given MDs,
  the sigma along the high side, lateral and along-hole axes (`sigma_hla`) and their three correlations
  (`corr_hl_ha_la`: high side-lateral, high side-along, lateral-along). The models are `iscwsa:MWD_Rev0` ("basic MWD") and
  `iscwsa:MWD_AX_Rev0` ("MWD with axial correction"); case 7 changes between them mid-well.
  - The `inputs` are `tie_on: zero_uncertainty`, the table's caption "uncertainty at the tie line (MD = 0) is zero": the
    tie-on slot is no error source and the first interval is not doubled. This differs from the `per_term_nev` files, which
    keep the slot as a source.
  - The other input is `toolface: borehole`, the borehole toolface of the paper's Appendix B.
- `total_nev` and `hla` files are described by `schemas/vectors.json`. Each records its `source`: the paper and the table,
  and the page where it is known.
- `conformance/manifest.json` maps each vector file to the model it exercises (for example `iscwsa:A001Mc`), and for
  `per_term_nev` the test well. File paths are relative to `conformance/`. A `total_nev` or `hla` file covers every well
  and case in it.
- Vectors are normative: they define the expected result.

## Rules

1. An engine MUST refuse a model that uses a term, weighting function, variable, unit or library capability
   it cannot evaluate. It MUST NOT skip the item or substitute zero.
2. A library's `requires` lists the capabilities needed beyond the base grammar. An engine that lacks any of
   them MUST refuse models that use that library.
3. An engine is conformant for a model if it reproduces that model's vectors within tolerance. The tolerance depends on the
   kind.
   - `per_term_nev`: at each station and term, `max|calc - ref| <= max(0.001 * max|ref|, 1e-4)` m^2, taken over the six
     printed covariance elements, where `max|ref|` is the station's largest printed element for that term. The 1e-4 m^2
     floor is two half-steps of the 4-decimal print of the covariances (+-5e-5 rounding each). The 0.1% relative part allows
     for the 2-decimal print of the station inclination and azimuth; the reference engine's worst relative difference above
     the floor on the 806 vectors is 0.05%. The tolerance is provisional, pending sub-committee review;
     [`deviations.md`](deviations.md) gives the evidence.
   - `total_nev`: each printed element within the paper's own criterion, `abs(calc - ref) <= 2` where `abs(ref) < 200`, else
     `abs(calc - ref) <= 0.01 * abs(ref)`. Provisional.
   - `hla`: each sigma within `max(0.005 * ref, 0.002)` and each correlation within 0.01 of the printed value. The 0.002 is
     the print step of the sigmas. Provisional.
4. Consumers MUST check `$schema` against the releases they support and refuse documents they do not recognise.

## Vertical reference

A `total_nev` vector may declare a `vertical_reference` input: a sigma (in m) that is added to VV, as sigma squared, at every station, because SPE 90408's Table 10 depth systematic reference (virtually a TVD reference error, independent of well bore direction) has no depth, inclination or azimuth weighting function. A calculation that is given no such input adds no term.

## Known misses

A `total_nev` file may list `known_misses`: printed values (model, well, MD and element) that an independent calculation does
not reproduce, each with its reason. They are disclosed, not tolerated silently. An engine passes the file if every other
value is within tolerance. The one listed, example model #1 on well 3 at 3000 m (NN), is a station-list difference: the paper
gives no station list. If an engine reproduces a listed value, that is worth reporting, not a failure.

## Capabilities

A library's `requires` array lists capabilities from this table. The rule is rule 2: an engine that does not support a listed
capability MUST refuse the library, and every model that uses it.

| Capability | Meaning |
|------------|---------|
| `xcl_position_direct` | The library's formulas use the previous-station variables `MDPrev`, `IncPrev` and `AzPrev`, and the XCLA and XCLH weighting functions are evaluated as position-direct (tangential) terms, as the XCL Supplement r16 describes, not through the usual weighting-function derivative matrices. |
| `gyro_modes` | The term needs the survey-mode switching of SPE 90408 Fig. C1, as `propagation.md` describes. The terms are the 15 that appear only on the `Tool Type: Gyro` sheets. An engine without them MUST refuse a model that uses one of these terms. |
| `bias_terms` | The term has propagation `Bias` (the SPE 67616 bias terms `DSTB` and `AMIB` in the ISCWSA MWD bias sheets). A bias term shifts the expected position; it does not add covariance. An engine that cannot apply it MUST refuse a model that uses it. |

## Vertical stations

The singularity formulas published for vertical stations (`singularity_north`, `singularity_east`, `singularity_vertical`) are
carried verbatim in the libraries. How an engine should treat a vertical station overall (the tie-on, and the derivation of
azimuth and dip there) is provisional, pending sub-committee review. The 806 vectors include vertical stations and are the
normative check. A reference description of the propagation will be published separately as `docs/propagation.md` (not yet
available). Until then, [`deviations.md`](deviations.md) lists the conventions the 806 vectors need that the published text
does not state, including two (the XCLA azimuth change after a vertical station, and the XYM3E/XYM4E first-station rule) that
the JSON cannot yet express.
