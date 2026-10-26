> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Changelog

## Unreleased

### Added (gyro modes, conformance)

- `docs/propagation.md`: how the formulas propagate into a covariance. It covers the position derivative, the propagation modes within a leg, across legs and across wells, the tie-on, vertical stations, the toolface, position-direct XCLA/XCLH and the gyro survey modes. Each rule names its published basis.
- `docs/deviations.md` rows C13 to C28: the gyro conventions with their failing counts, the SPE 90408 Table 10 vertical reference (25 of 492 printed values fail without it), the known miss of example model #1, the survey-leg rule and the SPE 67616 tie-on, and the provisional tolerance and term names.
- `gyro` object in the model: stationary and continuous survey modes with their own ranges and `init_inc`, the continuous running speeds, `min_distance`, `init_factor` and the xy accelerometer cant. The 10 gyro models carry both blocks of their sheets.
- SPE 67616 Table 3 (`hla`) and SPE 90408 Appendix E (`total_nev`) conformance vectors, with `known_misses` and the declared `vertical_reference`.
- The README status table now shows the load, self-check, 806, SPE 67616 and SPE 90408 results. The 10 gyro models load.

### Added (SPE 90408 examples)

- `iscwsa:spe90408` library: the SPE 90408 Table 1-4, 6 and 8 rows that no sheet carries.
- Six reference models `iscwsa:SPE90408_Ex1` to `Ex6` (Appendix D example models), in `conformance/models/iscwsa/`, built by `tools/make_spe90408.py`. Model `status` gains `reference`; `origin` is optional only for `reference` (published example) models.

### Added (all sheets)

- 129 models from every ISCWSA sheet (files 807, 808, 809, 1052), with 7 libraries: `iscwsa:rev0` to `rev5` and `iscwsa:rot6axis`. See the status table in the README.
- `term_groups`: terms that co-occur with equal magnitude and propagation are grouped.
- Per-term `requires`, so an engine can refuse a model whose terms need a capability it lacks (`gyro_modes`, `bias_terms`).
- Propagation `Bias` for the DSTB/AMIB terms of the ISCWSA MWD bias Rev0-2 sheets (docs/deviations.md C11).
- `Az` decided as the station's recorded azimuth (true) (docs/deviations.md C4).

### Errata (all proposed, pending sub-committee review)

Each entry is a correction to the sheet formula text; see `tools/errata.json` and `docs/deviations.md`.

| Entry | Status |
|---|---|
| `iscwsa:rev5` XYM3E inclination | proposed |
| `iscwsa:rev5` XYM3E azimuth | proposed |
| `iscwsa:rev5` XYM4E inclination | proposed |
| `iscwsa:rev5` XYM4E azimuth | proposed |
| `iscwsa:rev5` XCLA singularity_north | proposed |
| `iscwsa:rev5` XCLA singularity_east | proposed |
| `iscwsa:rot6axis` XYM3E inclination | proposed |
| `iscwsa:rot6axis` XYM3E azimuth | proposed |
| `iscwsa:rot6axis` XYM4E inclination | proposed |
| `iscwsa:rot6axis` XYM4E azimuth | proposed |
| `iscwsa:rot6axis` XCLA singularity_north | proposed |
| `iscwsa:rot6axis` XCLA singularity_east | proposed |
