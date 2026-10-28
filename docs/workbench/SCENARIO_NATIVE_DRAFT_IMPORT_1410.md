# #1410 Native XIHeadless scenario → untrusted offline draft-preview

Status: **L1 PROTOTYPE, DRAFT_ONLY; NOT a registered/imported catalog test or executable case.** No database, edit endpoint, publish, runner, lease, gameplay, or authorization. #1406 remains PRODUCT NOT ACCEPTED.

## Pinned native sources

Source repository: `sarthax/xiheadless-dsp`; inspected commit `159a5b9d4b4e43397bd509a816a7241a97511319`. Native input example: `scenarios/scenario_npc_event.json` (array of named steps with `do` and `expect` maps) and `docs/evidence/pr7-acceptance-2026-10-19/A06-1-probe/scenario.json` (A06 route probe). Relevant native vocabulary source: `Brains/ScenarioActionSchema.cs` / `ScenarioExpectationSchema.cs` on that revision. Native recognition is NOT execution or approved oracle proof. Importer uses deliberately narrow audited key subsets, so newer or other valid native keys become BLOCKED until independently reviewed.

The pinned source tree contained **10 top-level `scenarios/*.json` files**, plus historical acceptance probe `scenario.json` files (including multiple A06 expected-failure/fault-injection paths). These are *source paths*, NOT 10 approved runnable scenarios, and not the historical unverified 28/~12–14 count. A06 expected-failure membership must be owner-classified; a file name alone cannot certify intended test polarity.

## Offline API

`preview(raw: bytes, source_path, source_sha, repo_sha=PIN, expected_failure=False)` verifies an externally provided digest against bytes and **requires** the pinned repo revision string; it cannot independently prove the bytes actually came from that revision. It produces an untrusted, noncanonical JSON object with native action/expectation maps, readable source step labels, explicit UNKNOWN oracle verdicts and BLOCKED admission. Never import/execute the returned payload as trusted steps. `inventory(files, source_root, expected_fail_paths)` reports actual files examined/candidate previews/blocked errors; the CLI accepts an **already obtained directory**, does not download or mutate it. No owner selection or deduplication by semantic equivalence is attempted; names duplicate within a source are rejected, content digest is the candidate identity, and cross-file duplicates require owner reconciliation.

A source pin and input SHA are **provenance claims**, not signatures: downstream must verify source retrieval/authentication, schema version, any commit/object hash relationship, lease/permission, observer independence and oracle. Malformed JSON, non-array roots, duplicate step names, invalid timeout shape, stale source revision and digest mismatch reject. Unknown action/expectation keys or A06 ambiguity leave DRAFT_ONLY / BLOCKED, never silently drop steps. Even recognized cases remain DRAFT_ONLY / BLOCKED because publish/run/oracle review is not implemented.

Exact-head CI is a deterministic Python offline contract check. It cannot prove native runtime compatibility, authentic source data, gameplay verdict, or end-user acceptance.
