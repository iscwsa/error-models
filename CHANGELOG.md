> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Changelog

## Unreleased

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
