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

- `docs/` - the formula grammar (`grammar.md`) and the conformance rules (`conformance.md`).
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

The `iscwsa:rev5` library currently carries proposed errata (corrections to the spreadsheet formula text, each with its reason in `tools/errata.json`) that await a sub-committee decision.

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
