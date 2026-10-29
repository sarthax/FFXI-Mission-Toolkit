# End-to-end evidence pipeline validation — 2026-10-19

Goal: one reproducible XiHeadless -> Toolkit evidence run, no LLM-driven gameplay.
Result: **achieved** for the deterministic path; tool server registered and a grounded model-driven tool call demonstrated (section 7).

## 1. Revisions and workspace

| Repo | Branch @ SHA | Local state |
|---|---|---|
| Toolkit `<local Toolkit checkout>` | `main` fast-forwarded to `b42e0c65` (#1111); this work on `fix/supervisor-openapi-empty-paths-20261018` | untracked/modified files pre-existed (`docs/shift_report.log`, `data/assault/assault_reviews.db`, `data/root_archive/`, 4 `domains/definitions.d/*.json`) — untouched |
| XiHeadless `...\headless-research\xiheadless-dsp` | `main` @ `1c657bc46b7297479337b86027d9c15dfcc551d4` | **dirty, owned by another agent**: `Capabilities/Inventory.cs`, `Game/PacketParsers.cs`, `Game/WorldState.cs`, `Interfaces/IInventory.cs`, `Mcp/McpBrain.cs`, `tools/scenario_runner.py`. Not modified. The built `bin/mcp/XiHeadless.dll` includes these edits (sha256 recorded in each report). |
| DSP `<local DSP checkout>` | `main` @ `f2d771e0fc818cf2b2a65aea123253f5f4be438c` | `GIT_VER`, `data/` untracked |

`...\xiheadless` is the upstream JasonPulse clone and `...\xiheadless-repo-audit` is a clean audit copy; neither was used.

## 2. Supervisor gateway (tested against an isolated instance on 127.0.0.1:8421)

A second Toolkit process was started so the already-running 8420 instance (older code, no supervisor token) was not disturbed.
Launcher + env: `<local data dir>\start_toolkit.ps1`, `supervisor.env.ps1` (secrets, outside any repo).

| Endpoint | Result |
|---|---|
| `/health` | 200 `gateway: ready, results_configured: true`; 403 with no token; 403 with wrong token |
| `/service-health?service=ollama\|database\|dsp_map` | 200, `reachable: true`, `check: tcp_connect_only`; unknown name -> 400 |
| `/log-errors?source=dsp` | 200, real redacted lines from `<local DSP checkout>\log\map-server.log`; `headless` -> `configured:false, lines:[]` (explicit unconfigured) |
| `/test-runs`, `/failed-assertions` | 200; empty before import, 2 runs after (no failures) |
| `/test-character-inventory?charid=21836` | 200 with persisted rows; charid not on allowlist -> 400 |
| `/openapi.json` | **BUG FOUND**: `paths` was `{}` (see below). Fixed; now exactly the 6 GET operations. Still served unauthenticated (spec only). |

**Bug:** under FastAPI 0.141 (the Toolkit `.venv`) `include_router` yields lazy `_IncludedRouter` objects, so the route filter in `supervisor_openapi()` matched nothing. Fixed by building the spec from `router.routes`. The existing test `test_isolated_openapi_contains_only_read_only_supervisor_tools` covers it (it passed on system FastAPI 0.136 only); verified manually on both versions — pytest is not installed in either environment.

DB access uses a dedicated account `tk_supervisor_ro@127.0.0.1` with `GRANT SELECT ON dspdb_fresh.char_inventory` only (no other privileges).

## 3. XiHeadless MCP capabilities (live, char `Menro`, id 21836, account `xitest07`)

51 tools registered (`tools/list`). Verified working this session: `initialize`, `capabilities`, `snapshot`, `inventory`, `container_items` (0 bag, 1 Safe, 2 Storage), `key_items`, `party_status`, `nearby_entities`, `recent_chat`, `say` (read-only GM `!moghancement info`), `logout`.

- `snapshot` -> `{name,id,zone,inZone,x,y,z,hp,maxHp,mp,maxMp,tp,gil,mainJob,mainLevel,subJob,subLevel,engaged,serverStatus,dead,moving,eventActive,eventId,partyMembers}` (zone 235 Bastok Markets, lv1 WAR).
- `inventory` / `container_items` -> `[{slot,itemId,qty}]`; `key_items` -> `[ids]` (returned `[387]`); `recent_chat` -> `[{Kind,Sender,Message,Ms}]`.
- `capabilities` -> supports snapshot, movement, combat, magic, chat, events, zoning, party, inventory, trade, wait_for_event, resources, goal_persistence; **unsupported: wardrobes, auction_house, synthesis**.
- Registered but not exercised (mutating or out of scope): furniture_*, pot_*, move_to_container, trade_npc, combat/movement tools.

## 4. Client vs server comparison

Client (MCP, live) vs MariaDB via supervisor (persisted after clean logout), run `obs-20261019T065856Z` and repeat `obs-20261019T070215Z`:
- Bag: client `container_items 0` (9 rows incl. gil row slot0/65535) == DB `location 0` — identical.
- Mog Safe: client `container_items 1` (18 rows) == DB `location 1` — identical.
- Persistence delay: the runner polls the DB (45 s then 20 s steps, max 4) after logout; both runs matched on the first poll.
- Not compared: key items (no supervisor key-item endpoint; MCP shows `[387]`, GM info reports no held furniture KI), Safe 2, installed-furniture layout.

## 5. Scenario and verdict

Case `MOG-09` (moghancement, stage `key_item`): "stored but uninstalled furnishing grants none". Observation only; the sole chat command is read-only `!moghancement info`.
Assertions: expected char session; Safe holds furnishings with nonzero aura (precondition); active KI == oracle for empty layout (0); aura all zero; bag and Safe equal persisted rows. **Verdict PASS (both runs).**
Limits of this PASS: "uninstalled" is inferred from zero aura / KI 0 via GM info, not read from a layout; the catalog has no pure inventory-observation case, so MOG-09 is the closest honest fit.

Runner: `tools/observation_runner.py` (xiheadless-dsp). Reproduce:

```powershell
. <local data dir>\supervisor.env.ps1
py -3 tools\observation_runner.py --out-dir <local data dir>\artifacts\runN
python -m workbench.server_admin.feature_testing.importer --catalog data\testing\feature_test_readiness.json --database <local data dir>\feature_results.sqlite --report <local data dir>\artifacts\runN\report.json
```

Raw evidence: `<local data dir>\artifacts\run1|run2\{client_observations,persisted_inventory,report}.json`, `run1\discovery.json` (full tool schemas).
`headless_commit` is the real xiheadless git HEAD; the working tree was dirty (listed in each report's `provenance`).

## 6. Import status

Both reports imported (`Imported 1 evidence records`). Visible in `/feature-testing/results`, `/runs`, `/run/<id>`, `/catalog/moghancement/MOG-09`, and `/api/supervisor/test-runs`. No failures, so `/failed-assertions` stays empty (correct).

## 7. Open WebUI / Ollama

Open WebUI 0.11.0 on `127.0.0.1:3000` (8080 is another service). The user signed in; the agent registered the tool server in Admin -> Integrations -> External Tool Servers: type OpenAPI, base URL `http://127.0.0.1:8421`, spec path `api/supervisor/openapi.json` (the filtered spec only), auth Bearer, token entered in the API Key field only. "Verify" and Save both reported **Connection successful**. No CORS or auth changes were made (Open WebUI calls the tool server from its backend).

Prompt test ("Check the Mission Toolkit supervisor health, retrieve the latest test run, and summarize any failures. Use the configured tools and cite the observations you actually retrieved."). Models over 9B cannot run on this machine (`qwen3.8` 27B abandoned; task model set to `qwen2.5-coder:7b`).

**Attempt 1** (`qwen2.5-coder:7b`, default function calling): tool calls were printed as JSON text, with `"authorization": "string"` placeholders; nothing executed; reply ungrounded.
Root cause of the placeholders: the spec exposed `authorization` as a model-visible parameter. Fixed in `supervisor.py`: header param removed, `bearerAuth` security scheme declared per operation (valid token 200, no token 403; runtime auth unchanged).

**Attempt 2** (`qwen2.5:7b`, 7.6B, Function Calling = Native, only "Mission Toolkit Supervisor" enabled):

| Question | Observation |
|---|---|
| Tool discovery | Yes: called `supervisor_health`, `supervisor_test_runs`, `supervisor_failed_assertions`. |
| Valid parameters | Yes: calls executed with no token parameter. |
| Real data retrieved | Yes: gateway ready, execution disabled, results configured; runs `obs-20261019T070215Z` and `obs-20261019T065856Z`, both PASS, moghancement. |
| Missing evidence vs failure | Reported "no failures" from the empty failed-assertions list; correct. |
| Invented facts | None material. Mild embellishment: follow-up suggestions only. |

Conclusion: registration is secure and end-to-end grounded tool use works with a <=9B model once Function Calling is Native and the spec has no `authorization` parameter. One run only; reliability across prompts is not measured.

## 8. Gaps and blockers

- Port 8420 Toolkit instance runs old code without supervisor env; needs a restart by its owner.
- Toolkit `.venv` lacks `pytest` and `PyMySQL`; system Python has an antlr runtime mismatch. This run vendored PyMySQL into `<local data dir>\extra_site` on `PYTHONPATH`.
- Supervisor has no key-item endpoint, no Safe 2 / furniture-layout view, and `headless` log source is unconfigured.
- Importer `headless_commit` must be a git SHA, but the headless checkout has uncommitted changes, so the report is not exactly reproducible from the SHA alone (DLL hash recorded as compensation).
- Env-file pitfall hit during setup: writing Windows paths with `\f` through Python/shell escapes silently corrupted `MISSION_TOOLKIT_TEST_RESULTS_DB`; `health` still said `results_configured: true` because it only checks the variable is set, not that the file exists.

## 9. Recommended next steps

1. Merge the OpenAPI fix; restart 8420 with the supervisor env.
2. Open WebUI done; repeat the prompt test a few times / with other tools to measure reliability. Note `qwen3:8b` is in the Admin model list but missing from the chat selector (uninvestigated).
3. Add a supervisor key-item and furniture-layout read (fixed-query, allowlisted charid).
4. Add `results_db_exists` to `/health`.
5. Commit the other agent's headless work, then re-run so `headless_commit` is clean.
6. Add an inventory-observation catalog case rather than reusing MOG-09.

## 10. Reproducibility and MCP validation (follow-up, 2026-10-19)

**Reconciliation.** The "dirty" XiHeadless tree (Inventory.cs, PacketParsers.cs, WorldState.cs, IInventory.cs, McpBrain.cs) was byte-identical (CRLF-normalised) to `origin/main` (PR #1, `d4e38d3`); only the untracked `tools/scenario_runner.py` was older than origin's. Nothing needed committing. Backup: `D:\MissionToolkitData\artifacts\xih_dirty_backup_20261019\` plus a labelled stash entry; local `main` fast-forwarded to `origin/main` (2a5bc22).
PR #3 (`feature/observation-runner`): merged `origin/main` (`1369b1b`, merge commit, no force-push) and added a dirty-tree guard (`c607543d9da3b7ee911f7ddb87077cf49bc4e7e2`): the runner refuses tracked changes unless `--allow-dirty`, and records `headless_dirty_files` + DLL sha256.

**Clean build.** `dotnet build XiHeadless.csproj -c Release -o bin/mcp` from the committed tree at `c607543d9da3b7ee911f7ddb87077cf49bc4e7e2` -> `XiHeadless.dll` sha256 `ef3927a379f5b96f72329418fb12282da7c680a03dbf843fac213219b683a86b`.

| Run | Verdict | Assertions | dirty files |
|---|---|---|---|
| `obs-20261019T081629Z` | PASS | 6/6 | none |
| `obs-20261019T082001Z` | PASS | 6/6 | none |

Both report `headless_commit` `c607543d9da3b7ee911f7ddb87077cf49bc4e7e2`, were imported, and appear in `/api/supervisor/test-runs` (4 runs total with the two earlier dirty-tree runs). Artifacts: `D:\MissionToolkitData\artifacts\rebuilt1|rebuilt2`.

**Inventory capability (`inventory`, `container_items`).** Bag and Mog Safe match `char_inventory` locations 0 and 1 exactly (slot, itemId, qty) in all four runs, gil row (slot 0, item 65535) included. Gaps found by reading, not yet exercised live:
- Container numbering: DSP `CONTAINER_ID` is 8=Wardrobe, 9=Mog Safe 2, 10=Wardrobe 2, 11/12=Wardrobe 3/4. The `container_items` tool description says "8-9 wardrobes, 10 Safe 2", which disagrees. Needs a live check with a character holding Safe 2 items before anything changes; no packet handler was altered.
- `capabilities` lists wardrobes unsupported, so Safe 2 and wardrobes are unverified against DB.
- Safe (1) is only populated in a Mog House or after login. Storage (2), Temp, Locker, Satchel, Sack, Case are not compared (runner compares 0 and 1; the supervisor endpoint returns all locations).
- Not exposed: item extdata and equip state; not needed for slot/qty comparison.

**Key items.** MCP `key_items` returns ids decoded from the 0x55 packet (`table*512 + bit`, keyList only), so it reports what the server sent, not DB state. Authoritative persistence: `chars.keyitems` (blob) holding the raw `keyitems_t keys` struct (`tables[MAX_KEYS_TABLE=7]`, each keyList + seenList), written by `charutils::SaveKeyItems` (`UPDATE chars SET keyitems=... WHERE charid=...`). Saved immediately, not only at logout, on Lua add/del key item (`lua_baseentity.cpp`), client 0x64 seen-list updates (`packet_system.cpp`), and Moghancement change (`charentity.cpp`). Proposed read-only diagnostic: fixed endpoint `GET /api/supervisor/test-character-key-items?charid=` with the existing allowlist and `GRANT SELECT (charid, keyitems) ON chars` for `tk_supervisor_ro`; decode the blob server-side (bit i of keyList in table t -> id t*512+i) and compare with MCP `key_items`. No free-form SQL. Not implemented; confirm the `keyitems_t` byte layout before decoding.

**Remaining blockers.** 8420 Toolkit needs a restart with supervisor env; no key-item or Safe 2/furniture endpoints; no inventory-observation catalog case; PR #3 and #1112 await review/merge.
