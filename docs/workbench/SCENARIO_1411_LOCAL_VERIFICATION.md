# #1411 Scenario Developer typed steps: local verification

Evidence only. No behavior was changed. Nothing was run against a live client or game server.

- Date: 2026-10-27
- Toolkit commit tested: `0de12ff9ce06247a0ec8ea8039517703b34f39ab` (origin/main at the time; includes #1452-#1455)
- DSP checkout: a real local checkout (path omitted), as configured through a scratch settings DB
- XiHeadless checkout: `FFXI-Tools/headless-research/b-pr170` at `e5e8035071` (clean; the commit the Toolkit pins as `NATIVE_SCHEMA_HEAD`)

## Results

| Task | Result | One-line evidence |
|---|---|---|
| 1. Real catalog and pickers | PASS | NPC and zone pickers returned rows matching `sql/npc_list.sql` and `sql/zone_settings.sql`; provenance notes match the source rows |
| 2. Round trip with real IDs | PASS (1 bug) | 10-step draft saved, reloaded, restored, clean; Advanced JSON equals the builder export; delete flags unsaved in Guided mode. Bug: edits made in Advanced mode are silently lost |
| 3. XiHeadless acceptance | FAIL | Action-only steps are rejected by the runner loader (`expect must be object`). Check-only and `expect:{}` forms are accepted. The MCP task path accepts only `wait_ms` |
| 4. Controlled run | NOT_RUN | No authorized operator confirmed a safe live environment. Oracle UNAPPROVED, verdict UNKNOWN |

## What was run

- Toolkit: `uvicorn workbench.app.host:app` on `127.0.0.1:8431` from a worktree, with a scratch settings DB (`dsp_server_path` set to the real DSP checkout; file is gitignored), a scratch drafts DB (`MISSION_TOOLKIT_TEST_DRAFTS_DB`) and a throwaway 32+ character operator token. The real settings and drafts stores were not touched.
- Catalog queried over `GET /scenario-developer/catalog/search` with header `x-requested-with: toolkit-ui`, and through the page's own pickers.
- The builder and the page were driven by JavaScript in the in-app browser. The pane was hidden, so screenshots timed out. Everything below comes from DOM reads and HTTP responses, not a visual check.
- Task 3: the pinned-commit sources of `ScenarioFileValidation.cs`, `ScenarioActionSchema.cs` and `ScenarioExpectationSchema.cs` were compiled into a scratch console harness (net6 runtime; the .NET 9 runtime crashed with a CLR shadow-stack assert on this machine). The MCP gate sequence was copied by hand from `Mcp/ScenarioTaskTools.cs`. The prebuilt `bin/mcp/XiHeadless.dll` was **not** used: it was built 2026-10-20 19:47 PDT, before HEAD's commit time (2026-10-21T02:23 -07:00).

## Task 1: catalog and pickers

| Query | Result | Source check |
|---|---|---|
| NPC `Ulmia` | 12 returned (limit 12) of 41 matching rows | ids match `sql/npc_list.sql` rows (16801910, 16810216, 16814535, 16830612 ...) |
| NPC `Tamba` | `Tamba-Namba` 17105413 | matches `npc_list.sql` line 8497 (pos 104.979, 3.999, 21.244) |
| Zone `Windurst Woods` | id 241 | matches `zone_settings` row 241 |
| Zone `Mhaura` | 249, plus 221, 228, 47 (ship and sea routes) | — |
| NPC `zzzzqqq` (no match) | `choices: []`, HTTP 200 | — |
| NPC `a`, zone `e` (broad, limit 20) | capped at the limit | — |
| Empty query | 422 `catalog query must contain 1-64 characters` | — |
| Missing `x-requested-with` | 403 | — |

Picker UI (via the page): NPC `Tamba` filled `npc_id = 17105413`; zone `Windurst` offered 7 candidates and filled `zone = 241`. Provenance notes read, for example:
`Filled from the catalog: npc_id = 17105413 (Tamba-Namba) — unreconciled DSP source candidate from sql/npc_list.sql; not verified for this zone or client`.

Observations (not bugs):
- Ambiguous NPC names list only name and id. `Ulmia` has 41 rows across zones, and one is at (0,0,0), a dynamic entity, so an operator cannot tell which zone they are picking.
- Broad queries are truncated and the note says "bounded search" without saying how many more rows exist. For `a`, the exact-name match `A` ranks first.
- I did not check how the picker renders an empty result list.

## Task 2: round trip

Draft `inventory_observation/VERIFY-1411-01` (the page's seeded synthetic draft with the case id and title changed), saved as revision 1, DESIGN_ONLY. Composition: 4 reviewed pairs (navigate near, talk to npc, wait for state, recover hp), 3 action-only (`examine_npc`, `wait_ms`, `rest_hp`), 3 check-only (`zone`, `hpp`, `entities_gt`). Real IDs: NPC 17105413 in the talk and examine steps; zone 80 (Southern San dOria [S]) in the wait-for-state step and the zone check, both filled through the pickers.

| Check | Result |
|---|---|
| Save | "Saved DESIGN_ONLY inventory_observation/VERIFY-1411-01 revision 1. NOT reviewed or executable." |
| Reload, list, open | All 10 steps restored in order; "SAVED · no unsaved changes", revision 1 |
| Advanced JSON vs builder export | Same content after sorting keys (raw strings differ: the builder puts `name` first, the saved copy is key-sorted) |
| When/Then preview | Reads sensibly, e.g. `Walk to Tamba-Namba — navigate near — walk_to [104.979,3.999,21.244], then check x_near = 104.979` |
| Delete one step, Guided mode | `UNSAVED WORK · leaving this page will discard changes`, `UNSAVED revision 1`; Advanced JSON shows 9 steps |

Exported native JSON (`spec.native_steps.steps`):

```json
[
 {"name":"Wait in zone","do":{"wait_ms":1000},"expect":{"zone":80}},
 {"name":"Examine Tamba-Namba","do":{"examine_npc":17105413}},
 {"name":"Zone check","expect":{"zone":80}},
 {"name":"Pause","do":{"wait_ms":500}},
 {"name":"Walk to Tamba-Namba","do":{"walk_to":[104.979,3.999,21.244]},"expect":{"x_near":104.979}},
 {"name":"Talk to Tamba-Namba","do":{"talk_npc":17105413},"expect":{"event_active":true}},
 {"name":"Recover HP","do":{"rest_hp":50},"expect":{"hpp":50}},
 {"name":"Rest","do":{"rest_hp":80}},
 {"name":"HP check","expect":{"hpp":50}},
 {"name":"Entities check","expect":{"entities_gt":0}}
]
```

The `walk_to` coordinates are the NPC's own `npc_list` position: a source value, not checked with `!checknav`, and the NPC was not checked against zone 80. The `wait_ms` plus zone and `rest_hp` plus `hpp` pairings, and the values 50, 50 and 80, are mine, not source-backed.

Note on the "wait for state" and "recover hp" pairs: the JSON contains `wait_ms` and `rest_hp`, not the pair names.

## Task 3: XiHeadless acceptance, per key

Loaders tested: `ScenarioBrain.Load` (runner, `XI_SCENARIO`; calls `ScenarioFileValidation.CheckStructure`) and `ScenarioTaskTools.Start` (MCP `task_scenario_start`; same `CheckStructure`, then more gates). The `ScenarioBrain.Load` path beyond `CheckStructure` was read, not run. There is no separate "importer" in this XiHeadless commit.

"Alone" means the step shape the Toolkit emits (no `expect` for action-only; no `do` for check-only).

| Key | Side | Alone | With `"expect":{}` | MCP `task_scenario_start` |
|---|---|---|---|---|
| walk_to | do | REJECT `step_0: expect must be object` | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| talk_npc | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| examine_npc | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| event_update | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| event_finish | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| wait_ms | do | REJECT (same) | ACCEPT | ACCEPT (only key that passes) |
| rest_hp | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| invite | do | REJECT (same) | ACCEPT | REJECT `scenario_legacy_actions_not_supported` |
| accept_invite | do | REJECT (same) | ACCEPT | REJECT `scenario_legacy_actions_not_supported` |
| engage | do | REJECT (same) | ACCEPT | REJECT `scenario_resource_actions_not_yet_supported` |
| x_near | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| event_active | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| event_id | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| event_param0 | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| zone | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| hpp | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| party_members_gt | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |
| entities_gt | expect | ACCEPT | n/a | REJECT `scenario_expectations_not_yet_supported` |

Value shapes for `walk_to`: `[x,y,z]`, `[x,z]` and `{coords, timeout_ms, stall_ms}` are accepted; an object without `coords` is rejected (`walk_to.coords: expected finite [x,z] or [x,y,z]`). Other shapes: empty `expect` with no `do` is rejected (`empty expect with no do asserts nothing`); a step with neither side is rejected.

Full Task 2 export:

| Input | Runner loader | MCP |
|---|---|---|
| As saved (10 steps) | REJECT: `step_1`, `step_3`, `step_7` `expect must be object` | same |
| `"expect":{}` added to the action-only steps | ACCEPT | REJECT `scenario_expectations_not_yet_supported` |
| The four reviewed pairs only | ACCEPT | REJECT `scenario_expectations_not_yet_supported` |

Answers:
- One-sided steps: **check-only is accepted; action-only is rejected** by the runner loader. The Toolkit emits action-only steps and reports them valid.
- Value shapes: accepted as listed above.
- Whether the runner executes accepted steps was not tested.

## Task 4: controlled run

NOT_RUN. No authorized operator confirmed a safe environment, and Task 3 showed the Toolkit's action-only output would not load. Oracle UNAPPROVED; verdict UNKNOWN. Nothing here is a PASS for gameplay behavior.

## Bugs found

1. **Toolkit and XiHeadless disagree on action-only steps.** `validate_native_steps` accepts a step with `do` and no `expect`; `ScenarioFileValidation.CheckStructure` rejects it (`expect must be object`). Repro: save any action-only step and feed the export to the runner loader. Fix options: export `"expect":{}`, or relax `CheckStructure`.
2. **Typed-builder edits made in Advanced mode are silently lost.** Repro: open the saved draft; click Advanced (the typed builder stays visible and editable); click Remove on a builder step (builder shows 9); the state still reads "SAVED · no unsaved changes" and Advanced JSON still has 10 steps; click Guided; the builder is back to 10 with no warning. Cause: in Advanced mode the draft comes from the Advanced JSON text only (`scenario_developer.js` around lines 868-872). Nothing saved is corrupted.
3. **`invite` and `accept_invite` are not in `ScenarioActionDispatcher.TypedActionNames`.** The MCP task path rejects them as legacy actions, though the Toolkit offers them as reviewed actions. Related finding: the MCP task path accepts only `wait_ms` and refuses every `expect`, so a "valid native draft step" is mostly not runnable there.

## Open questions

- Does the runner (`ScenarioBrain`) execute each accepted key as the Toolkit's templates assume? Not tested.
- Which fix for bug 1 does the owner want: Toolkit side or XiHeadless side?
- Does the picker show a clear empty state for a no-match search? Not checked visually.
- The `walk_to` position and the NPC-in-zone relationship are unverified (no `!checknav`, no zone check).
- The prebuilt XiHeadless DLL is older than the pinned commit; it was not tested.
- Visual rendering of the page was not checked (the pane was hidden).

## Reproduction

The harness (3 copied sources, `Program.cs`, `cases.tsv`) was kept outside the repo. To redo Task 3: compile those three files from `Brains/` at `e5e8035071` with `LangVersion 12`, call `ScenarioFileValidation.CheckStructure` on each case, and apply the `ScenarioTaskTools.Start` gates in the order shown there.

## Runner follow-up (2026-10-28, main at `da4c4970`)

Evidence only; no Toolkit or XiHeadless behavior was changed.

### Offline (Toolkit side)

| Command (repo root) | Result |
|---|---|
| `pytest test_fixtures/test_native_steps_schema_1411.py test_fixtures/test_scenario_typed_steps_1411.py test_fixtures/test_typed_action_library_1409.py` | 116 passed |
| `pytest test_fixtures/test_scenario_typed_library_contract_1409.py test_fixtures/test_test_catalog_browse_1410.py test_fixtures/test_research_runner.py` | 16 passed |
| `pytest test_fixtures/test_scenario_developer_host_page.py` | 1 failed: `TypeError: ord() expected string of length 1, but int found` inside the installed `antlr4` package (environment, not the repo; not investigated further) |

These tests pin the Toolkit's export (`"expect": {}` for action-only steps, #1457/#1461) and the `observed_paths` table against a mirror of the loader rules recorded above. They do not run the real C# validator. Re-running the compiled `CheckStructure` against the post-#1461 export: NOT_RUN.

### One live run (owner-confirmed, read-only)

- Server: the already-running local DSP test server (not restarted, reset or reimported; MariaDB only read). The XiHeadless checkout at `e5e8035071` with its prebuilt `Debug/net9.0` DLL (built 02:24, after the pinned commit time), launched through its own `scripts/run_dsp.py` with the documented default test account and a pool lease.
- Scenario (one step, written outside the repo): `do: {walk_to: [641.03, -1.398, 316.0]}`, `expect: {x_near: 641.03, radius: 1.5}`. The target is the DB start x plus 8 on the same z; it was **not** checked with `!checknav`, only run through the runner's own navmesh (`North_Gustaberg.nav` loaded).
- Character position (zone 106), from the `chars` table before the run: `(633.03, -1.398, 316.0)`.
- Runner result: **FAIL**. The `walk_to` action was reported `completed`, `Verified: true`, in 1319 ms, but the bot's own state stayed at `(638.8, -1.4, 316.0)` for the rest of the 40 s window: `x_near: want 641.03±1.5 got 638.8` (2.2 short of the target).
- Character position from the `chars` table after logout: `(633.64, -3.1, 311.19)`. This is not the end-of-step position: the bot "retreated before the logout hold", so the DB readback cannot confirm 638.8 either.
- Conclusion: the loader accepted a `walk_to` + `x_near` pair and the runner dispatched the walk and moved the character about 5.8 units toward the target. The step did **not** pass, and no independent readback confirms the final position. This is **not** a PASS for movement. Whether the stop short is a navmesh/arrival-tolerance behavior or a target that is off-mesh is unknown. Repeating with a navmesh-checked target is NOT_RUN.
- The `x_near` default radius is 5, so a short walk (for example +3) would pass without moving. A live movement check needs a target farther than the radius from the start.

## Recommendation for #1459 (invite / accept_invite and the MCP path)

Evidence: at `e5e8035071` `task_scenario_start` accepts only `wait_ms` and no `expect`; `invite` and `accept_invite` are rejected as `scenario_legacy_actions_not_supported` because they are missing from `ScenarioActionDispatcher.TypedActionNames`, which is a different (and fixable) cause from the other keys' `..._not_yet_supported`. The file loader accepts all 18 keys.

Proposed (owner decision):
1. Toolkit, now: keep the `observed_paths` snapshot, and show it as "file runner: accepted / MCP task path: rejected (reason)" beside each key. Do not label any key "runnable" on the MCP path other than `wait_ms`. This is already what the builder shows; the remaining work is to make the per-key table visible in the step list as a whole, not only the chosen step.
2. XiHeadless, separate decision: either add `invite`/`accept_invite` to `TypedActionNames` (they already have legacy handlers), or document that party actions are file-runner only. Not decided here, and not a Toolkit change.
3. Keep `execution_tested: false` for every key. The single live observation above (`walk_to` + `x_near`, FAIL) is not enough to change it for any key.
