# Run context for Compare runs (#1408 / #1467) - environment_fingerprint and fixture_context

Status: smallest reversible version. Definitions below are an OWNER DECISION PENDING; nothing here is a claim that two runs are equivalent beyond string equality.

## What the importer and Compare runs do (read from code, unchanged)
- `importer.validate_report`: both fields are optional `evidence` keys, non-empty text, max 256 chars. Not derived, not parsed.
- `stored_run_comparison.comparison_context`: takes a field only if every row of the run agrees; else it is left out.
- `revision_comparison._gate`: a pair is comparable only when DSP commits differ, definition digests match, and both fields are present and EQUAL (plus schema version). Missing -> `*_MISSING`, different -> `*_MISMATCH`.

## Definitions (derived by `feature_testing/run_context.py`, offline, writes a new report file)
- `environment_fingerprint` = `headless_dll_sha256=<hex>;headless_tree=<clean|dirty:<12 hex>>`. From `observations.provenance` (the observation runner records the XiHeadless DLL hash and dirty-file list). The DSP/toolkit/headless commits are already separate columns. NOT recorded anywhere: DSP working-tree dirtiness, DSP database/SQL state, server config, client build.
- `fixture_context` = `character_id=<id>;zone_id=<id>;stored_furnishing_item_ids=<sorted ids>`. From `observations.snapshot` and `observations.stored_furnishing_item_ids`. MOG-09 receipt shape only; other shapes get no value.
- A field is added only when all its inputs are present and typed correctly; an existing value is never overwritten.

## Usage
`python -m workbench.server_admin.feature_testing.run_context --report old.json --out new.json`, then import `new.json` with `importer` into a SCRATCH database. The importer's `record_sha256` covers the report as imported, so a derived copy hashes differently from the original; keep the original.

## Result on the three recorded MOG-09 receipts (scratch DB, never the live store)
- 2026-10-21 FAIL vs PASS (same character, build, DSP commit): environment and fixture now match; NOT_COMPARABLE only for `SAME_DSP_REVISION`.
- 2026-10-19 PASS vs either 2026-10-21 run: `ENVIRONMENT_MISMATCH` (different XiHeadless build, dirty tree) and `FIXTURE_CONTEXT_MISMATCH` (different character, zone 235 vs 106, different stored items).
- So no REAL pair is comparable. That is the correct answer: the only runs on different DSP commits also differ in build and fixture. A comparable pair is exercised in tests with a synthetic DSP commit, labelled as such.

## Open questions for the owner
1. Should the character id / zone be part of the fixture, or only the stored-item set? (Including them makes any two different disposable characters incomparable.)
2. Should a dirty XiHeadless tree make a run incomparable, or only a different DLL hash?
3. Should the observation runner (outside this repo) write these fields itself instead of this post-hoc derivation? The runner script is not in the repo.
4. DSP-side environment (database/SQL state, config) is unrecorded; what must be captured?
