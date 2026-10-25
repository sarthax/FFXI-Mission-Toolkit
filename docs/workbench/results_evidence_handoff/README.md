# Results v2 evidence handoff — authentic MOG-09 receipts (DRAFT)

Coordinator #1348 · Results epic #1408 · Evidence discovery #1419 · Fixture PR #1417 · UX PR #1418.
Read-only collection. No live server, gameplay, DB write or rerun was performed. The Toolkit instance on 8420 was only read; a second
read-only instance (8423, copy of the results DB plus the FAIL report imported into the **copy**) was used to render the FAIL page.
No file owned by #1417, #1418 or Agent E (#1201) was edited. This PR adds only `docs/workbench/results_evidence_handoff/**`.

**Result for #1419: the gap is NOT confirmed. Authentic MOG-09 run receipts exist locally** (5 reports, 2 characters, PASS and FAIL).
Everything below is recorded evidence; anything not recorded is listed as missing, not inferred.

## 1. Evidence inventory

Source roots (outside any repo, on the operator machine): `<DATA_DIR>\artifacts\…` and `<USER_HOME>\AppData\Local\MissionToolkit\test_execution\…`.
Paths are redacted here; the retrieval steps for the owner are in section 7.

| Run id | Observed (UTC) | Char | Recorded verdict | Persisted rows after save | Polls | Toolkit / XiHeadless / DSP | Sample here |
|---|---|---|---|---|---|---|---|
| `obs-20261021T025326Z` | 2026-10-21 03:03:04 | Routhu (21833) | **FAIL** (assertions 5, 6 not ok) | 0 | 4 | e4fff3f7 / b3c10c09 / 68343227 | `samples/fail_obs-20261021T025326Z/` |
| `obs-20261021T040036Z` | 2026-10-21 04:02:39 | Routhu (21833) | PASS | 9 | 1 | 88d5f62e / b3c10c09 / 68343227 | `samples/pass_obs-20261021T040036Z/` |
| `obs-20261019T065856Z` | 2026-10-19 07:01:03 | Menro (21836) | PASS | 27 | 1 | 700213b6 / 1c657bc4 / f2d771e0 | `samples/pass_obs-20261019T065856Z/` |
| `obs-20261019T070215Z`, `…T081629Z`, `…T082001Z` | 2026-10-19 | Menro | PASS (3 further reports) | — | — | see `feature_results.sqlite` | not copied (same shape) |

Per-run files (all sanitized, source format preserved): `report.json` (schema_version 1, the importer input), `client_observations.json`
(snapshot, key_items, bag, safe, safe2, party, capabilities, gm_info), `persisted_inventory.json`. The FAIL run also has
`job_lifecycle_row.json` (the runner job row: `status COMPLETED`, `phase evidence_imported`, `verdict FAIL`, timestamps, `error null`).

Source fingerprints of the **original (unsanitized)** report files, so a reviewer can match them on the owner machine:

| Run | sha256 of original `report.json` |
|---|---|
| obs-20261021T025326Z | `590ac96fa492811aad10ffa52ea34a7b6a52e390b5aa6c47a89b056b2c09ef20` |
| obs-20261019T065856Z | `fc5fc07c564c9dc8326a701f1432af651018c4da67340f18db89119e7459904b` |
| obs-20261021T040036Z | `3c073e51748a10014124ec24df6da05564af6939fd030e4316ae55486fc50e01` |

The sanitized copies hash differently on purpose (account name and local paths replaced). Sanitizing was limited to: `xitest##` account names ->
`<test-account>`, local user/data paths -> `<USER_HOME>` / `<DATA_DIR>`. Character names and ids are disposable test characters and were kept.
A scan for token/password/secret/bearer/authorization found nothing in any copied file; the supervisor env and lease files were never opened.

What each run records (and what it does not):

| Item | Recorded? |
|---|---|
| Scenario definition + version | **No.** Report carries `case_id`, `feature_id`, `stage` only. The Toolkit joins a catalog entry (`feature_test_readiness.json`, state `seeded_legacy_example`) at read time; the importer does not pin a specification revision (the UI says so). |
| Run id, observed time | Yes. No start/end/duration; one `observed_at`. |
| Expected / observed per assertion | Yes, `evidence.assertions[]` = `{name, expected, observed, ok}`. |
| Runner-computed verdict | Yes (`verdict`), origin = the runner script, imported unauthenticated. |
| Per-step outcome | Only as assertions. Step ids (MOG-09-S01..S06) and ordering come from the Toolkit specification, not the report. |
| Lifecycle | Only for the FAIL run (`test_jobs.db` row); the Oct 19 runs have no job row in any store I found (not proven that none existed). |
| Event trace / chat log / screenshot | **None.** Only `gm_info` (4 lines of `!moghancement info` output) and raw JSON. No in-game screenshot exists. |
| Source revisions | Yes: dsp, headless, toolkit commits; headless DLL sha256; dirty-file list. No fingerprint of the report itself. |
| Hash/signature of the report | No. |

## 2. Readable interpretation (FAIL run `obs-20261021T025326Z`)

- **Tested:** MOG-09 — furnishings kept in the Mog Safe but not installed must not activate a Moghancement; the client's view of the bag and Safe must equal the saved server rows.
- **What happened in game:** read-only. The runner logged in the disposable character (Routhu, zone 106), read inventory, Safe, key items, and ran the read-only GM command `!moghancement info`. It then polled the server DB four times after logout. Nothing was changed.
- **Expected:** an active key item of 0, all eight aura values 0, and client bag/Safe equal to the persisted rows.
- **Observed:** key item 0 and aura all zero (steps 1–4 consistent with expectation). Client bag had 8 rows and the Safe had 1 row (item 3); the persisted `char_inventory` read returned **0 rows on all 4 polls**. Steps 5 and 6 therefore failed.
- **Supported verdict:** FAIL on the stated assertions (client rows != persisted rows). That is all the evidence supports.
- **Not established:** *why* the DB read was empty. Candidates include the save not having flushed, a wrong or empty read, or a real persistence defect; the receipt cannot distinguish them. Run `obs-20261021T040036Z`, same character about an hour later, persisted 9 rows and passed, which is a hint, not an explanation.
- **Could not be verified:** installed-furniture layout (assumed empty), held key items vs persisted key items (no endpoint), that client and DB values did not come from one runner (they do), the character approval (`charid` is runner-reported), any independent authentication of the report. The Toolkit marks all of these `NOT_ESTABLISHED`, correctly.
- **Lifecycle vs verdict:** the job reached `COMPLETED / evidence_imported` while the verdict is `FAIL`. Task completion must not be shown as success.

PASS runs: same scenario, every assertion `ok`; the same limits apply. A PASS here is a recorded runner verdict, never independent gameplay proof.

## 3. Current UI (screenshots in `ui_snapshots/`)

| File | Shows |
|---|---|
| `01_run_history_FAIL_plus_4_PASS.jpg` | Run History tab (`/feature-testing`): run id, last observation, features, verdict counts, records. 8423 copy. |
| `02_run_detail_FAIL_top.jpg` | Result header: recorded FAIL, recalculated FAIL, "Steps PASS (recalculated only): 4/6", independent verification NOT_ESTABLISHED. |
| `03_run_detail_FAIL_step5_6.jpg` | Per-step cards, expected vs observed panels for the failed steps. |
| `04_run_detail_PASS_live_8420_halfres.jpg` | PASS run on the real 8420 instance (half resolution). |
| `05_api_results_raw_json.jpg` | `/feature-testing/results` is raw JSON including `evidence_json` as an escaped string. |
| `06_run_not_found_json_404.jpg` | Missing-data state: unknown run id returns bare `{"detail":"Run not found"}`. |

These show the current screen only. They are not proof that any run was correct.
Observed UI defects, by evidence: step 5 summary prints `bag_matches_persisted = (large value)`; the "Expected outcome" panel shows the
rule in words, not the persisted value (which is `[]` in the report); the server-side value is never shown next to the client value
(in the report, `expected` holds the persisted side and `observed` the client side, which is easy to misrender). `/runs` and `/results` are JSON only (no HTML) outside the Run History tab.
A FAIL-with-failed-job state, a BLOCKED state and a cancelled state were **not** available: no such receipts exist.

## 4. Field-by-field mapping

| Results v2 field | Existing source | Availability | Work |
|---|---|---|---|
| Scenario title / purpose / Given-When-Then | `feature_test_readiness.json` + specification, joined by case_id | Available | format |
| Scenario version pinned to the run | none (importer does not pin; runs pin only code commits) | **Missing** | backend: store spec hash/revision in the receipt |
| Run id, observed time | `results.run_id`, `observed_at` | Available | format |
| Start time, end time, duration | job row has created/updated only; report has one time | Partial | backend: runner to record start/end |
| Lifecycle status (queued/running/complete) | `jobs.db` row | Available for runs started through the job table (1 of 5) | format + join by run_id |
| Expected outcome per step | `assertions[].expected` + spec text | Available | format (render value, not only prose) |
| Observed value per step | `assertions[].observed` | Available | format; stop `(large value)` truncation; show both sides |
| Per-step verdict | assertion `ok`; Toolkit recalculates | Available | format |
| Overall verdict + origin | `verdict` (runner), recalculated (Toolkit) | Available, both shown | format; keep "recorded vs recalculated" labels |
| Independent verification | always `NOT_ESTABLISHED` | Available (as a constant) | format |
| Source revisions | dsp/headless/toolkit commit, DLL sha, dirty files | Available | format |
| Report integrity (hash/signature) | none | **Missing** | backend: hash on import |
| Step evidence: logs / events / chat | `gm_info` only (4 lines) | Mostly missing | backend: runner must capture, e.g. `recent_chat`, `wait_for_event` |
| Screenshots | none exist | **Missing** | out of scope for headless; do not invent |
| Cause of a FAIL | none | **Missing** | backend: persist poll history (timing, row counts) not just final |
| Run comparison | 5 receipts incl. FAIL then PASS on one char | Partial | backend: stable receipt ids + common step ids; format afterwards |
| Cleanup / teardown record | spec text only | Missing for runs | backend |

**Formatting only:** title, steps, expected/observed (with both sides), verdict labels, revisions, history table, lifecycle join, limitation badges.
**Needs backend:** spec revision pin, start/end times, report hash, persistence poll history, captured event/chat logs, receipt/step identifiers for comparison, cancel/BLOCKED states (no receipts exist).

## 5. Blockers and unknowns

1. Only MOG-09 has receipts. No authentic NPC, zone, party or inventory-scenario run exists in these stores, so Results v2 cannot be validated against those from real data.
2. Scenario Library scenarios (PR #1414) have no execution receipts; the library is not execution-validated.
3. No BLOCKED, CANCELLED or UNKNOWN receipt exists; those states stay synthetic (#1417).
4. The FAIL's cause is unknown (section 2).
5. Receipts are unauthenticated runner output imported as-is.
6. The reports sit on one operator machine; this PR carries sanitized copies only.

## 6. Minimum functional Results UI (recommendation)

1. History list: run id, time, case, verdict, lifecycle status (kept separate from verdict).
2. Detail header: recorded vs recalculated verdict and "independent verification: NOT_ESTABLISHED" as today.
3. Step table: step name, expected value, observed value (both client and persisted sides shown), pass/fail, source label. No truncation.
4. Evidence panel: revisions + raw `report.json` download or link; limitations list.
5. Explicit empty/missing states: "no event log recorded", "no start/end recorded", "run not found" as a page, not bare JSON.
6. Comparison: defer until receipt/step ids exist; a two-run side-by-side of the FAIL and next PASS is a good first target.

Build and test against `samples/*`. Fixtures there are real recorded data; do not edit values.

## 7. Owner retrieval steps (originals)

Originals: `<DATA_DIR>\artifacts\mog09-540ec235a4cc49fb91fb28ce97d7cdf4\`, `<DATA_DIR>\artifacts\run1\`, and
`<USER_HOME>\AppData\Local\MissionToolkit\test_execution\artifacts\mog09-0528c156632245f2aa8d3277ade1dab3\`. Verify with the sha256 table above.
Importer used: `python -m workbench.server_admin.feature_testing.importer --catalog data/testing/feature_test_readiness.json --database <db> --report <report.json>`
(imported only into a scratch copy for this work).

## 8. Coordination

#1419 asks for a read-only locate-and-adapter investigation; this finds the receipts, so #1419 need not end as GAP CONFIRMED. A proposed
null-safe adapter mapping is the table in section 4. Not duplicated here: #1417 fixtures, #1418 UX journey, Agent E lifecycle UI.
