# Automated Testing Integration & MCP Readiness — 2026-10-18

Toolkit main 925fa79 (PR #1100). Running DSP: <local DSP checkout> @ f2d771e0fc (main), DB dspdb_fresh.
Live automation was run later the same day (see section 6); no push/merge done.

## 1. Integration health
- Toolkit GUI: /feature-testing, /catalog, /results, /runs, scenario pages and drill-down work against a temp DB.
  Empty/missing DB handled, pages read-only (405 on writes), 404s clean.
- BUG FOUND+FIXED (local, uncommitted): every HTML page returned 500 (`current_theme` undefined) because the
  router's own Jinja2Templates lacked host globals. Fix in `_host_impl.py` after include_router; regression test
  added (skips when host deps unavailable). One stale test assertion updated (collision-case wording).
- Env gap: Toolkit .venv has no pytest/httpx2, system Python cannot import host (antlr) — new test unverified under pytest.
- Oracles: gardening_results.sql and item_furnishing.sql match the live DB.

## 2. Oracle findings
- Gardening: CalculateResults is deterministic given (plant, crystal1, crystal2, pot strength 0-31, config).
  Strength is random at plant but pinnable via `!garden strength N`. Oracle currently range-checks; it can be
  upgraded to exact item+quantity. Config flags garden_*_matters = 0 on the running server.
- Moghancement: oracle matches UpdateMoghancement (dominant element, strongest piece, first-found tie).
  Minor eligibility difference to reconcile. Levels KEY_ITEM_PASS / MODIFIER_PASS / BEHAVIOR_PASS stay separate.

## 3. XiHeadless MCP capability matrix (refreshed after live campaigns)
| Operation | Status | Where |
|---|---|---|
| Login / disposable char pool | WORKING (runner forces Bastok nation, offline, test accounts only) | tools/mcp_client.py, tools/char_pool.py, tools/scenario_runner.py |
| Say / GM command send | WORKING | tool `say`, McpBot.gm() |
| Capture GM response text | WORKING (chat offset 24 fix) | `recent_chat` |
| Wait for events | WORKING | `wait_for_event` |
| Inventory + Mog Safe 1/2 inspection | WORKING | `inventory`, `container_items` |
| Move item bag<->safe | WORKING | `move_to_container` |
| Mog House enter/exit | WORKING | `enter_mog_house`, `exit_mog_house` |
| Furnishing place/remove/finalize (0x0FA/0x0FB, finalize runs Moghancement recalc) | WORKING | `furniture_place`, `furniture_remove`, `furniture_finish` |
| Observe key items | WORKING | `key_items`, `!moghancement info` |
| Observe modifiers | PARTIAL | only via GM chat output; no behavior deltas yet |
| Plant/feed/examine/dry/harvest flowerpot (0x0FC-0x0FF) | WORKING | `pot_plant`, `pot_examine`, `pot_dry`, `pot_harvest` |
| Advance growth | WORKING via GM | `!garden grow/mature/strength` |
| Inventory deltas | WORKING (bag and both Safes) | `container_items` diffs |
| Relog persistence | WORKING | McpBot.close()/new session |
| Cancellation / watchdog | WORKING | McpBot.cancel()/abort() |
| Telemetry feeds to Toolkit | WORKING | JSONL via FileTelemetryBridge |

## 4. Runner integration proposal
Extend, don't replace: add `tools/scenario_runner.py` on top of McpBot/char_pool.
- Scenario spec = Toolkit catalog scenario id + variable dict; one worker per leased character.
- Bounded campaigns (N iterations, seeded), sequential per char, parallel across pool leases.
- Heartbeat + per-step timeout via rpc timeout; cancel via McpBot.cancel; recovery = release(crashed=True) + re-lease.
- Evidence = assertions + observations (chat lines, inventory deltas, GM info output) written as importer schema v1 JSON.
- Output imported with `importer.py` into the SQLite DB named by MISSION_TOOLKIT_TEST_RESULTS_DB.
- Never emit PASS without observed evidence; unobservable stages are BLOCKED.

## 5. Scenarios
- A (Moghancement, 10 steps): lease char; GM-grant furniture items; enter Mog House; (BLOCKED: install tool) use
  `!moghancement info/recalc` after GM-placed furnishings; read output via recent_chat; assert KI -> KEY_ITEM_PASS only;
  `!getmod`-style read for MODIFIER_PASS; relog; assert persistence; clear.
- B (Gardening, 10 steps): batch preferred: for each (plant, c1, c2, strength) from gardening_batch_plan.json:
  `!garden` plant with `strength N`, `!garden grow`, harvest via GM, compare items to exact oracle; mixed/uniform pots.
  Needs plant/harvest observation: GM-only path works if `!garden info` output is capturable.
- C (Behavior): wilt-duration modifier compare vs baseline; Money/Money II gil over repeated kills (statistical trials);
  crafting skill; replacement/removal. Needs modifier + gil observation; BEHAVIOR_PASS only from measured deltas.

## 6. First-run readiness (live results)
- Campaign run against the live DSP with real packets and no LLM: 35 evidence records imported into a temp results DB, all PASS.
  - Moghancement: MOG-01/02/03/04/06/08/10/12/13 (single and multi-item, both Safes, ties, relog persistence, clear, rejected forced KI).
  - Gardening: GARD-02 (crystal combos), GARD-03 (all four seeds at pot strength 0/31), GARD-06 (full-Safe harvest blocked then delivered once), GARD-08 (repeat harvest adds nothing).
- Oracle finding: the C++ reward quantity uses float32; the Toolkit oracle was corrected (`_f32`, test added) after a live mismatch.
- Nation control: all runs observed nation 1 (Bastok).
- Not covered: modifier and behavior deltas (gil/Money, wilt duration), and whether the oracle's within-combo row order matches the server's load order.

## 7. Backlog (priority)
1. Modifier/behavior measurement tests (Money gil trials, wilt duration).
2. Commit XiHeadless to git (currently untracked; headless_commit is a DLL SHA1) and settle licence/docker questions.
3. Add pytest/httpx2 to Toolkit .venv (pip SSL gap).
4. Verify oracle row ordering against server load order.
5. Push the Toolkit branch and open a PR (needs approval).

## 8. Decision table
| Component | Current status | Can run tests? | Missing work |
|---|---|---|---|
| Toolkit Results | Works (after local fix) | Yes (import/view) | Commit fix; venv test deps |
| Toolkit Test Inventory | Catalog complete | Yes | None blocking |
| Gardening SQL Oracle | Exact, float32-correct | Yes | Row-order check |
| Moghancement Oracle | Matches C++ | Partly | Eligibility nit; behavior effects |
| XiHeadless MCP | Furnishing, pot, Safe and KI tools working | Yes | Modifier/behavior observation |
| DSP GM Diagnostics | `!garden`, `!moghancement` present | Yes | Confirm output capturable |
| Automated Runner | tools/scenario_runner.py | Yes (35 PASS) | Behavior cases, git tracking |

Next: hand to git agent for branch push/PR; local follow-up is behavior (modifier) tests.
