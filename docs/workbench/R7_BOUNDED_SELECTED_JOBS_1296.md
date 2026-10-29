# R7 P0 — Bounded selected job / level observation (draft PR under #1296)

## Verified source references, not deployed authority

- [DSP repository `sql/char_stats.sql`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/sql/char_stats.sql) defines `charid` primary key and four **unsigned TINYINT** persisted fields: `mjob`, `sjob`, `mlvl`, `slvl`.
- [DSP repository `src/map/utils/charutils.cpp`](https://github.com/sarthax/darkstar-to-valhalla/blob/main/src/map/utils/charutils.cpp) reads persisted `char_stats.mjob,sjob` during load and later assigns in-memory job levels from a separate job-level source; do not assume these persisted selected-level fields always match the current live server or running client.
- No verified installed DSP schema, grant, source fingerprint or sample character was available in this GitHub-only implementation. The SQL fields are **source candidates** for an operator-verified deployment, not a guarantee of installed schema compatibility.

## Read-only supervisor endpoint

`GET /api/supervisor/test-character-selected-jobs?charid=<approved_disposable_character>`

Authentication and access: existing supervisor bearer token (minimum configured secret length), approved-character ID allowlist, `_approved_connection` loopback MySQL, explicit read-only transaction and fixed parameterized SELECT. No other endpoints or execution authorization added. The HTTP listener itself must be configured loopback-only by the operator; bearer authentication does not establish client-IP scope.

The fixed scoped queries select existence from `chars` and `mjob,sjob,mlvl,slvl` from `char_stats` for the exact approved `charid`; `LIMIT 2` detects unexpected duplicates. The DB account needs effective **SELECT-only on `chars` and `char_stats`**. Grants are not installed or modified by this PR.

On a well-shaped persisted row, response returns four raw integers: `selected_jobs.main_job_id`, `support_job_id`, `main_level`, `support_level`. Zero is preserved, not rewritten as absent or interpreted as job unlock/availability. Only unsigned-byte integers 0–255 from the documented SQL schema are accepted. No inferred job name, level cap, combat capability, quest outcome or currency.

Source type `persisted_db_not_live_memory`, UTC observation timestamp, source/schema/deployed revision `UNKNOWN`, `client_agreement=UNKNOWN`, `execution_enabled=false`. `supported_fields_complete=true` only means one valid persisted row had all four fields. **Full progression `complete=false` always**, and `job_unlock_status`, `quest_status`, `currencies` remain `UNSUPPORTED`.

Explicit negative states: `UNAVAILABLE` for missing database setup, `UNKNOWN_CHARACTER` if approved ID has no `chars` record, `INCOMPLETE_MISSING_CHAR_STATS` if no `char_stats` record, `INCOMPLETE_AMBIGUOUS_CHAR_STATS` if multiple rows, `INCOMPLETE_INVALID_PERSISTED_FIELDS` for NULL, absent or wrong-type values. Unauthorized char ID is rejected at the existing allowlist gate (HTTP 400); unauthorized bearer rejected before DB (HTTP 403). Database privilege, transport or schema errors emit sanitized HTTP 503; do not mislabel as ABSENT or VALID. All results are small and bounded (one 4-field response, maximum two fetched rows).

## Synthetic GitHub acceptance

Focused `R7 Bounded Selected Jobs Offline` workflow executes `test_fixtures/test_bounded_selected_jobs_r7.py`. It tests existing and absent character, missing or duplicated stats row, valid zero, NULL/string/bool/fractional/out-of-range/missing fields, SELECT/grant/schema failures with rollback/close, unconfigured DB, unauthorized char/bearer, scoped fixed SELECT-only query shape, and coexistence with existing inventory-v2 and progression routes. Required additional checks: Workbench Regression and Src Layout Regression. **Green GitHub CI is not gameplay acceptance.**

## Future operator-controlled local acceptance (not executed or assigned)

1. Confirm deployed DSP source and config SHA via DSP #59; inspect exact running `char_stats` schema rather than relying on repository SQL. Validate that persisted `mlvl/slvl` are meaningful for this DSP build and when updated relative to `char_jobs` / in-memory recalculations.
2. Configure a disposable approved character, loopback HTTP listener and DB user with effective SELECT on exactly `chars` and `char_stats`. Confirm unrelated-table and all INSERT/UPDATE/DELETE rights are absent. Do not record token or password in evidence.
3. Check authorized char vs unauthorized/unknown; valid 0 vs missing/NULL fields; stale/unavailable schema; source revision UNKNOWN versus independently attested. Record timestamp and save/restart boundary.
4. Capture matching character/client job IDs and levels from a separately authorized observation with known timing and source; if incomparable, classify UNKNOWN/NOT_COMPARABLE, never claim a live gameplay PASS.
5. No packet, GM, local DSP query, database mutation, XiHeadless runtime or scenario promotion is authorized by this draft. Keep #1296 OPEN for full quest/job unlock/currency coverage.

### Database setup failure cleanup hardening

The shared Toolkit `_approved_connection` path now closes its cursor and connection when either the read-only transaction declaration or transaction start fails; rollback failure does not prevent best-effort close. The existing `_open` driver variants also close a newly established connection if cursor creation fails. Synthetic failure-injection tests exercise these conditions; neither the failure nor the database credentials are placed in the HTTP response. These are **shared read-only helper safeguards**; they do not add privileges or establish effective deployment grants. Production MySQL/DSP connection behavior remains operator acceptance, not GitHub CI proof.
