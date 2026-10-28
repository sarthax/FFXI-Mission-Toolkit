# Native XiHeadless scenario importer (#1410 slice 5)

Module: `src/workbench/server_admin/feature_testing/native_scenario_importer.py`. Offline, design-only. It does not run, schedule,
publish or approve anything, and does not touch a live client, server or the live Toolkit data.

## What it does
1. Resolves a **pinned** commit (40-char sha) in a local XiHeadless git checkout and reads the scenario files as **git blobs at
   that commit** (never the working tree, no network). Discovery: `scenarios/*.json` and `docs/evidence/**/scenario.json`
   (other JSON, e.g. `docs/schemas/`, is not a scenario and is ignored).
2. Reviews every step of a scenario with `typed_action_library.review_native_steps`. A scenario is imported **only if every step
   is SUPPORTED**; otherwise the whole scenario is rejected and listed with per-step status and reasons. Nothing is trimmed,
   translated or dropped (no partial scenarios).
3. Adds a **DRAFT** revision with `test_catalog.add_revision`, feature `native_xiheadless_import`, case id derived from the path,
   source `import:<repo>@<full sha>:<path>`, tags `native-import`, `xiheadless` (+ `a06-probe` for `A06-` paths). Re-running is
   idempotent (identical content is reported `unchanged`). `--dry-run` writes nothing.
4. Records, inside each draft's `authoring.blocking_gaps`: source identity, that the oracle is unreviewed (the spec shape needs one
   placeholder assertion, `oracle_unreviewed`; it asserts nothing about the scenario), and the **open owner questions** (is this a
   wanted case; under which feature/case/tags). A06 paths additionally say polarity (pass-expected vs fail-expected) is NOT
   classified and no verdict is assumed.
5. **Deduplication**: only *exact* duplicates (identical parsed step array incl. names, values, timeouts) are merged; the first path
   in sort order is kept and the others are named in the draft and the report. Same action/check *shape* with different values is
   only **reported** (`near_duplicate_shapes`), never merged.

`timeout_ms` is a per-step field of the native files that `native_steps` cannot keep, so by default every step that has it is
rejected (the library's own fail-closed rule). `--carry-step-timeouts` is an explicit opt-in that removes it before review and
records the original value in the step's note and in the draft's gaps. Whether timeouts should be modelled is an owner decision.

## CLI
```
PYTHONPATH=src python -m workbench.server_admin.feature_testing.native_scenario_importer \
  --source-root <local XiHeadless checkout> --sha <40-char sha> --scratch-db <NEW absolute .sqlite> \
  [--carry-step-timeouts] [--dry-run] [--report out.json]
```
`--scratch-db` is required, must be absolute, must not exist (unless `--allow-existing-db`), and must not be the database named by
`MISSION_TOOLKIT_TEST_DRAFTS_DB`; the variable is set for this process only.

## Real run (pinned `sarthax/xiheadless-dsp@e5e80350711d5d2ec814c893a17c63baf3ef98a9`, scratch DB only)
28 scenario files: 10 under `scenarios/`, 18 under `docs/evidence/pr7-acceptance-2026-10-19/` (13 `A06-*`, 4 `A11-*`, 1 `probe`).
24 distinct contents (4 files merged as exact duplicates: `A06-4-temp-block` into `A06-3-jitter`, `A06-6-cancel5` into
`A06-6-cancel2`, `A11-2-invite-absent-member` and `scenarios/scenario_party_member.json` into `A11-1-leader-member-member`).

| Mode | Imported (DRAFT) | Rejected scenarios |
|---|---|---|
| default (strict) | 0 | 24 of 24 (all 52 steps carry `timeout_ms`) |
| `--carry-step-timeouts` | 10 (scratch DB: 10 revisions, 10 DRAFT events) | 14 |

Carry-mode rejections by reason (step counts): 11 more than one check in a step; 5 more than one action; 6 both; unreviewed actions
`say` (A06-2-bind), `patrol`, `sweep_npcs`; unreviewed check `in_zone` (4 steps); `walk_to` in `{x,y,z,timeout_ms}` object form
(A06-1-probe; the library accepts only `{coords,...}`). Imported: the 8 shortest A06 probes (walk_to/wait_ms + `zone`), `A06-1-probe2`
and `probe`. Eight of them share one shape and are listed as near-duplicates, not merged. None has an approved oracle; the A06
ones keep an open polarity question.

This shows the importer and the library agree on what they model; it does not show any scenario is correct, supported by the
runner, or safe to run. Nothing was run (NOT_RUN: any execution, native-runtime compatibility, live DB).
