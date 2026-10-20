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
   station's largest printed element for that term. The 1e-4 floor is two print steps: the vector files print covariances with
   4 decimals (+-5e-5 rounding) and the station inclination and azimuth with 2 decimals, so a tighter criterion would test the
   print format, not the engine. This tolerance is provisional until Plan 2.
4. Consumers MUST check `$schema` against the releases they support and refuse documents they do not recognise.
