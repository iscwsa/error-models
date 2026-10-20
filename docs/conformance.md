> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Conformance

Conformance vectors let an implementation check that it evaluates a model the way the ISCWSA intends.

## Vectors

- Vectors come only from published diagnostics. The current set is ISCWSA's "ErrorModelDiagnostics Rev5-1"
  (iscwsa.net file 806) for ISCWSA test wells 1-3, in `conformance/vectors/iscwsa_rev5-1/`.
- The vector files are ISCWSA's own published output, unchanged (byte-for-byte; sha256 values are in that
  directory's `README.md`).
- `conformance/manifest.json` maps each vector file to the model it exercises (for example `iscwsa:A001Mc`)
  and the test well. File paths are relative to `conformance/`.
- Each file gives the well reference parameters, the compiled error sources, and, per survey station, the
  covariance (NN, EE, VV, NE, NV, EV in m^2) contributed by each term plus a `TOTAL` row.
- Vectors are normative: they define the expected result.

## Rules

1. An engine MUST refuse a model that uses a term, weighting function, variable, unit or library capability
   it cannot evaluate. It MUST NOT skip the item or substitute zero.
2. A library's `requires` lists the capabilities needed beyond the base grammar. An engine that lacks any of
   them MUST refuse models that use that library.
3. An engine is conformant for a model if it reproduces that model's vectors within tolerance. At each station and term,
   `max|calc - ref| <= max(0.01 * max|ref|, 1e-4)` m^2, taken over the six printed covariance elements, where `max|ref|` is the
   station's largest printed element for that term. The 1e-4 m^2 floor is about two half-steps of the 4-decimal print of the
   covariances (+-5e-5 rounding each); the station inclination and azimuth are printed with only 2 decimals, which is a further
   reason not to tighten it. The 1% relative part is a provisional choice that matches the reference engine; it is not derived from
   print precision. The tolerance as a whole is provisional, pending sub-committee review.
4. Consumers MUST check `$schema` against the releases they support and refuse documents they do not recognise.

## Capabilities

A library's `requires` array lists capabilities from this table. The rule is rule 2: an engine that does not support a listed
capability MUST refuse the library, and every model that uses it.

| Capability | Meaning |
|------------|---------|
| `xcl_position_direct` | The library's formulas use the previous-station variables `MDPrev`, `IncPrev` and `AzPrev`, and the XCLA and XCLH weighting functions are evaluated as position-direct (tangential) terms, as the XCL Supplement r16 describes, not through the usual weighting-function derivative matrices. |

## Vertical stations

The singularity formulas published for vertical stations (`singularity_north`, `singularity_east`, `singularity_vertical`) are
carried verbatim in the libraries. How an engine should treat a vertical station overall (the tie-on, and the derivation of
azimuth and dip there) is provisional, pending sub-committee review. The 806 vectors include vertical stations and are the
normative check. A reference description of the propagation will be published separately as `docs/propagation.md` (not yet
available).
