> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Error Model Sub-Committee

> [!IMPORTANT]
> This page work in-progress and subject to change without notice.

Welome to the ISCWSA Error Model sub-committee GitHub repository.

# Mission
The role of the ISCWSA Error Model Maintenance Group is to define the mathematical framework for modeling the uncertainty in wellbore surveying. This allows different companies to implement a consistent set of algorithms for error modeling. The committee also defines a set of generic, conservative tool-codes for use when specific service provider tool-codes are not available.

> [!TIP]
> In general, ISCWSA does not define or supply the detailed magnitudes (error models, tool codes or IPM files) for a particular survey tool.

# Projects

## Error Model JSON Schema

> [!CAUTION]
> **NOT PRODUCTION READY!**

> [!WARNING]
> This schema and any models are a work in-progress and published only for testing and review.

---
### PROJECT GOALS

1) Create a JSON schema to support a common Error Model exchange format within OSDU and the industry at large.

2) Migrate current Error Model definitions from Excel to schema-compliant JSON. Legacy models (Rev0-4 ISCWSA MWD) are included.

---
### TECHNICAL DETAILS

**Layout.** `schemas/` holds the JSON Schemas (`model.json`, `library.json` and their sub-schemas), `library/<ns>/` the term libraries, and `models/<ns>/` the error models, where `<ns>` is the namespace. Qualified names are written `<ns>:<name>`, e.g. the library id `iscwsa:rev5`. The other directories:

- `docs/` - the formula grammar (`grammar.md`), the conformance rules (`conformance.md`), and where the libraries and the reference results differ from the published sources (`deviations.md`).
- `tools/` - the reference tools: formula parser and evaluator, spreadsheet extractor, validator, diagnostics reader, hashing and identity.
- `conformance/` - ISCWSA's published diagnostics, unchanged, as test vectors, and `manifest.json` mapping each file to the model it exercises.

**Namespaces.** A namespace matches `^[a-z][a-z0-9_]{1,31}$`. Reserved namespaces:

| Namespace | Contents |
|---|---|
| `iscwsa` | ISCWSA MWD and ISCWSA RCS models, and all ISCWSA libraries |
| `generic_iscwsa` | Generic ISCWSA models (the OWSG Rev5.1 sets A and B donated to ISCWSA) |
| `owsg` | Earlier OWSG releases (none yet) |

The registry is `namespaces.json`. A namespace is added by pull request with sub-committee approval. The rule is enforced only by this repository's CI (`validate.py --registry`); the schemas accept any syntactically valid namespace, so third parties can use their own.

Namespace UUID: `7c9fcf73-f032-422d-b9aa-a2d69fa46e1d`

**Versioning.** Schemas, libraries and models share one repository version. A release is a git tag. `$schema` and `$id` URLs carry the tag (`https://raw.githubusercontent.com/iscwsa/error-models/<tag>/schemas/model.json`); before the first release they use `main`.

**Identifiers.** Every `uuid` is a UUIDv5 (RFC 4122) of the namespace UUID above and an input string: for a model `<ns>:<id>` (its namespace and id), for a library its `library_id`, and for a library entry `<library_id>/<weighting_function|term>/<name>`, where the middle part says whether the entry is a weighting function or a term (so one of each with the same name stay distinct).

**Hashes.** `hash_function` is `SHA256` and `hash_value` is the lowercase hex SHA-256 over the RFC 8785 canonical JSON of the document without `hash_value` and `$schema`.

**Tools.** Install `tools/requirements.txt`, then from the repository root:

- `python -m tools.validate --registry .` validates every library and model (schemas, formulas, hashes, identifiers, namespaces). Proposed errata are reported as warnings; `--release` turns them into errors.
- `python -m tools.extract_xlsx --workbooks <dir> --sheet <sheet name> --library <id>` regenerates a library and its model from the ISCWSA spreadsheets, applying `tools/errata.json`.

The `iscwsa:rev5` and `iscwsa:rot6axis` libraries currently carry proposed errata (corrections to the spreadsheet formula text, each with its reason in `tools/errata.json`) that await a sub-committee decision. `docs/deviations.md` lists them with the evidence, together with the evaluation conventions the diagnostics need.

### MODEL STATUS

All 129 models extracted from the ISCWSA spreadsheets (7 libraries). What each check means:

- **round trip**: every term code and magnitude in the JSON equals the sheet (`tests/test_extract.py::test_all_magnitudes_round_trip`).
- **self-check**: every term covariance is finite at every station of wells 1-3 inside the model's applicability.
  The east-west exclusion geometry is an assumption (`docs/deviations.md`).
- **806**: station/term checks passed against ISCWSA's Rev 5.1 diagnostics (conformance rule 3). Only the two models
  the diagnostics exercise have a count. The rest read "formula from source, not validated numerically".
- **loaded / refused**: whether the engine accepts the model. A model is refused when it needs a capability the engine does not have yet.

The load, self-check and 806 results come from a private DGI engine check that reads this JSON and uses published sources only.

| model_id | sheet | library | status | load | round trip | self-check | 806 | notes |
|---|---|---|---|---|---|---|---|---|
| `generic_iscwsa:A001Mc` | MWD+SRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | 19476/19476 |  |
| `generic_iscwsa:A001Mc_Fl` | MWD+SRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A002Mc` | MWD+SRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A002Mc_Fl` | MWD+SRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A003Mc` | MWD+SRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A003Mc_Fl` | MWD+SRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A004Mc` | MWD+SRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A004Mc_Fl` | MWD+SRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A005Mc` | MWD+IFR1 | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A005Mc_Fl` | MWD+IFR1_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A006Mc` | MWD+IFR1+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A006Mc_Fl` | MWD+IFR1+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A007Mc` | MWD+IFR1+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A007Mc_Fl` | MWD+IFR1+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A008Mc` | MWD+IFR1+MS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A008Mc_Fl` | MWD+IFR1+MS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A009Mc` | MWD+IFR1+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A009Mc_Fl` | MWD+IFR1+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A010Mc` | MWD+IFR1+SAG+MS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A010Mc_Fl` | MWD+IFR1+SAG+MS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A011Mc` | MWD+IFR2+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A011Mc_Fl` | MWD+IFR2+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A012Mc` | MWD+IFR2+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A012Mc_Fl` | MWD+IFR2+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A013Mc` | MWD+IFR2+SAG+MS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A013Mc_Fl` | MWD+IFR2+SAG+MS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A014Mc` | EMS+SRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A014Mc_Fl` | EMS+SRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A015Mc` | EMS+SRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A015Mc_Fl` | EMS+SRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A016Mc` | EMS+SRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A016Mc_Fl` | EMS+SRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A017Mc` | EMS+SRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A017Mc_Fl` | EMS+SRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A018Mb` | DIPMETER | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A018Mb_Fl` | DIPMETER_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A019Gb` | GYRO-MWD | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A019Gb_Fl` | GYRO-MWD_Fl | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A020Gb` | GYRO-NS | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A020Gb_Fl` | GYRO-NS_Fl | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A021Gc` | GYRO-NS-CT | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A021Gc_Fl` | GYRO-NS-CT_Fl | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A022Gb` | CB_Film_GMS | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A022Gb_Fl` | CB_Film_GMS_Fl | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A023Gb` | CB_Film_GSS | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A023Gb_Fl` | CB_Film_GSS_Fl | `iscwsa:rev5` | current | refused | pass | — | — | needs gyro_modes (not yet supported) |
| `generic_iscwsa:A024Mb` | CB_Film_MMS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A024Mb_Fl` | CB_Film_MMS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A025Mb` | CB_Film_MSS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A025Mb_Fl` | CB_Film_MSS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A026Ua` | BLIND | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A026Ua_Fl` | BLIND_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A027Ub` | INC-ONLY | `iscwsa:rev5` | current | refused | pass | — | — | refused: sheet gives no XCLTortuosity |
| `generic_iscwsa:A027Ub_Fl` | INC-ONLY_Fl | `iscwsa:rev5` | current | refused | pass | — | — | refused: sheet gives no XCLTortuosity |
| `generic_iscwsa:A028Ub` | INC-ONLY_PLANNED_5_DEG | `iscwsa:rev5` | current | refused | pass | — | — | refused: sheet gives no XCLTortuosity |
| `generic_iscwsa:A028Ub_Fl` | INC-ONLY_PLANNED_5_DEG_Fl | `iscwsa:rev5` | current | refused | pass | — | — | refused: sheet gives no XCLTortuosity |
| `generic_iscwsa:A029Ub` | UNKNOWN | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A029Ub_Fl` | UNKNOWN_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:A030Ua` | ZERO-ERROR | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B001Mc` | MWD+HRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B001Mc_Fl` | MWD+HRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B002Mc` | MWD+HRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B002Mc_Fl` | MWD+HRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B003Mc` | MWD+HRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B003Mc_Fl` | MWD+HRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B004Mc` | MWD+HRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B004Mc_Fl` | MWD+HRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B005Mc` | MWD+HRGM+SAG+MS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B005Mc_Fl` | MWD+HRGM+SAG+MS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B006Mc` | MWD+LRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B006Mc_Fl` | MWD+LRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B007Mc` | MWD+LRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B007Mc_Fl` | MWD+LRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B008Mc` | MWD+LRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B008Mc_Fl` | MWD+LRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B009Mc` | MWD+LRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B009Mc_Fl` | MWD+LRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B010Mc` | EMS+IFR1+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B010Mc_Fl` | EMS+IFR1+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B011Mc` | EMS+IFR1+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B011Mc_Fl` | EMS+IFR1+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B012Mc` | EMS+IFR1+SAG+MS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B012Mc_Fl` | EMS+IFR1+SAG+MS_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B013Mc` | EMS+HRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B013Mc_Fl` | EMS+HRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B014Mc` | EMS+HRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B014Mc_Fl` | EMS+HRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B015Mc` | EMS+HRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B015Mc_Fl` | EMS+HRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B016Mc` | EMS+HRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B016Mc_Fl` | EMS+HRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B017Mc` | EMS+LRGM | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B017Mc_Fl` | EMS+LRGM_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B018Md` | EMS+LRGM+AX | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B018Md_Fl` | EMS+LRGM+AX_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B019Md` | EMS+LRGM+AX+SAG | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B019Md_Fl` | EMS+LRGM+AX+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B020Mc` | EMS+LRGM+SAG | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B020Mc_Fl` | EMS+LRGM+SAG_Fl | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B021Ga` | FINDS | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `generic_iscwsa:B022Ua` | BLIND+TREND | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:A001Mc` | ISCWSA MWD+SRGM Rev5 | `iscwsa:rev5` | current | loaded | pass | pass (0 stations excluded) | 19476/19476 |  |
| `iscwsa:A003Mc` | ISCWSA MWD+SRGM+AX Rev5 | `iscwsa:rev5` | current | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:D007Ma` | Candidate_Rot_6Axis_MWD+SRGM | `iscwsa:rot6axis` | candidate | refused | pass | — | — | refused: sheet gives no XCLTortuosity |
| `iscwsa:MWD_AX_Rev0` | ISCWSA MWD+AX Rev0 | `iscwsa:rev0` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_Rev1` | ISCWSA MWD+AX Rev1 | `iscwsa:rev1` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_Rev2` | ISCWSA MWD+AX Rev2 | `iscwsa:rev2` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_Rev3` | ISCWSA MWD+AX Rev3 | `iscwsa:rev3` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_Rev3_Fl` | ISCWSA MWD+AX Rev3_Fl | `iscwsa:rev3` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_Rev4` | ISCWSA MWD+AX Rev4 | `iscwsa:rev4` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_SAG_Rev0` | ISCWSA MWD+AX+SAG Rev0 | `iscwsa:rev0` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_SAG_Rev1` | ISCWSA MWD+AX+SAG Rev1 | `iscwsa:rev1` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_SAG_Rev2` | ISCWSA MWD+AX+SAG Rev2 | `iscwsa:rev2` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_SAG_Rev3` | ISCWSA MWD+AX+SAG Rev3 | `iscwsa:rev3` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_AX_SAG_Rev3_Fl` | ISCWSA MWD+AX+SAG Rev3_Fl | `iscwsa:rev3` | superseded | loaded | pass | pass (108 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev0` | ISCWSA MWD Rev0 | `iscwsa:rev0` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev1` | ISCWSA MWD Rev1 | `iscwsa:rev1` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev2` | ISCWSA MWD Rev2 | `iscwsa:rev2` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev3` | ISCWSA MWD Rev3 | `iscwsa:rev3` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev3_Fl` | ISCWSA MWD Rev3_Fl | `iscwsa:rev3` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_Rev4` | ISCWSA MWD Rev4 | `iscwsa:rev4` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_SAG_Rev0` | ISCWSA MWD+SAG Rev0 | `iscwsa:rev0` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_SAG_Rev1` | ISCWSA MWD+SAG Rev1 | `iscwsa:rev1` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_SAG_Rev2` | ISCWSA MWD+SAG Rev2 | `iscwsa:rev2` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_SAG_Rev3` | ISCWSA MWD+SAG Rev3 | `iscwsa:rev3` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_SAG_Rev3_Fl` | ISCWSA MWD+SAG Rev3_Fl | `iscwsa:rev3` | superseded | loaded | pass | pass (0 stations excluded) | formula from source, not validated numerically |  |
| `iscwsa:MWD_bias_Rev0` | ISCWSA MWD bias Rev0 | `iscwsa:rev0` | superseded | refused | pass | — | — | needs bias_terms (not yet supported) |
| `iscwsa:MWD_bias_Rev1` | ISCWSA MWD bias Rev1 | `iscwsa:rev1` | superseded | refused | pass | — | — | needs bias_terms (not yet supported) |
| `iscwsa:MWD_bias_Rev2` | ISCWSA MWD bias Rev2 | `iscwsa:rev2` | superseded | refused | pass | — | — | needs bias_terms (not yet supported) |

111 loaded, 18 refused (10 need `gyro_modes` and 3 need `bias_terms`; 5 have no `XCLTortuosity` value in the sheet).

---
### LINKS

- [JSON Schema Reference](https://json-schema.org/understanding-json-schema/reference)
- [Sub-Commitee Page](https://www.iscwsa.net/committees/error-model)
- [Error Model Documentation](https://www.iscwsa.net/error-model-documentation)
  - [Release Notes](https://www.iscwsa.net/media/files/files/41658d23/release-notes-iscwsa-error-model-revision-5-beta_68MWHmu.pdf) (.pdf)
  - [Rev5 Definition](https://www.iscwsa.net/media/files/files/64bd61c2/definition-of-iscwsa-error-model-v5-13.pdf) (.pdf)
  - [XCL Supplement](https://www.iscwsa.net/media/files/files/65e684c6/xcl-error-supplement-r16.pdf) (.pdf)
  - [Geomagnetic Models](https://www.iscwsa.net/media/files/files/c23e8374/five-primary-geomagnetic-reference-model-categories-rev2.pdf) (.pdf)
- [ICSWSA MWD Error Models](https://www.iscwsa.net/files/809) (.xlsx)
- [ISCWSA Rotating Continuous 6-Axis MWD](https://www.iscwsa.net/files/1052) (.xlsx)
- [Generic Error Models SetA Rev5-1](https://www.iscwsa.net/files/807) (.xlsx)
- [Generic Error Models SetB Rev5-1](https://www.iscwsa.net/files/808) (.xlsx)
- [ISCWSA MWD Diagnostics Rev5-1](https://www.iscwsa.net/files/806) (.zip)

---
### FAQS
- TODO
