> [!NOTE]
> This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.

# Releasing

Schemas, libraries and models share one version. A release is a git tag `vMAJOR.MINOR.PATCH`, and the files of a release
carry the tag in their URLs (`https://raw.githubusercontent.com/iscwsa/error-models/<tag>/schemas/model.json`). Between
releases they carry `main`. `tools/release.py` moves a tree from one to the other. A person tags; nothing is tagged or
published automatically.

| Part | Raised by |
|------|-----------|
| MAJOR | a schema change that makes a valid file invalid, or changes what a field means |
| MINOR | new models, libraries or optional fields, or accepted errata |
| PATCH | corrections to metadata or text that change no magnitude or formula |

The first release is `v0.1.0`. `v1.0.0` waits for the sub-committee's approval of the format.

## Before a release

- Every erratum in `tools/errata.json` is decided (`accepted` or `rejected`): `validate --release` treats a `proposed`
  one as an error, and `cut` refuses while there is one.
- `CHANGELOG.md` has the release's changes under `## Unreleased`.
- The workbooks are at hand for the determinism check (`python -m tools.extract_xlsx --check --workbooks <dir>`): the
  committed libraries and models must be exactly what the workbooks give.
- The tree is committed, on a branch for the release PR.

## Cut

`python -m tools.release cut vX.Y.Z --workbooks <dir>` (or `--no-workbooks`, and the release notes then say the check
was skipped). It refuses, and writes nothing, when any of these hold:

- the version isn't `vX.Y.Z`;
- the tree isn't at `main`;
- the tree has uncommitted changes;
- the version is already a tag, or isn't after the last one;
- `validate --release --registry` reports anything;
- `## Unreleased` is empty;
- a generated file differs from its committed one.

Then it:
1. rewrites every `/main/` URL in `$schema`, `$id` and `const` to the tag. The hash excludes `$schema`, so no
   `hash_value` changes; a cut that would change one stops (`HASH_CHANGED`);
2. copies the rewritten schemas into `tools/schemas/<tag>/`, where the validator looks for a release's schemas;
3. turns `## Unreleased` into `## vX.Y.Z (date)`, and adds the models and libraries added, changed (by `hash_value`) and
   removed since the previous tag.

Every file is written in one step that puts the tree back as it was if a write fails.

## Tag

Merge the release PR, and tag the merge commit `vX.Y.Z`. The `release` workflow then runs
`python -m tools.release check --tag vX.Y.Z`: every file at that release, the schema copies equal to `schemas/`, a
changelog section for it, and the validator clean. It fails when the tag doesn't name the files' release.

## Reopen

`python -m tools.release reopen`, on a second PR straight after the tag, points every file back at `main` and opens an
empty `## Unreleased`. `tools/schemas/<tag>/` stays, so files of that release still validate. Until it merges, `main`
validates as the release, and no other PR may merge: a file added at `main` in that window fails
`python -m tools.release check` in the `validate` workflow. Run twice, or before any cut, `reopen` changes nothing.

## If something goes wrong

- **`cut` refused.** Its error names the reason (`DIRTY`, `NOT_VALID`, `EMPTY_UNRELEASED`, `NOT_NEWER`, `EXISTS`,
  `NO_WORKBOOKS`, `NOT_DETERMINISTIC`, `HASH_CHANGED`, `NOT_MAIN`, `BAD_VERSION`). Nothing was written; fix it and run
  again.
- **The release PR needs changes.** Close it, change the tree at `main`, and cut again; or `reopen` on the branch, change
  it, and cut again.
- **A wrong tag was pushed.** The `release` workflow fails on it. Delete the tag before anyone relies on it, and tag the
  right commit.
- **A file merged at `main` between the tag and the reopen.** `check` names it; the reopen PR brings it back in line.

## Open questions

These are for the sub-committee; the tooling decides none of them:

- who approves a release and who may tag it;
- the license for the schemas, libraries and models, and for the workbooks the extractor reads;
- whether releases are signed;
- stable download URLs for the workbooks, so CI can run the extractor's determinism check.
