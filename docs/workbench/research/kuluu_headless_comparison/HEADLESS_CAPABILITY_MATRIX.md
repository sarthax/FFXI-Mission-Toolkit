# Headless capability matrix: our XiHeadless-DSP vs Kuluu

Audit date 2026-10-18. Status vocabulary: Verified working / Implemented but untested / Partial / Mock/simulated / Documented only / Missing / Unknown.

## What "our headless" actually is (inventory)

**It is not inside `<local>/mission_toolkit`.** The headless client lives in `<local>/FFXI-Tools\headless-research\xiheadless-dsp` (C# .NET 9, not a git repository). It is a DSP port of the upstream `JasonPulse/xiheadless` (LandSandBoat target). The Mission Toolkit only *consumes* its telemetry (live-client feed) and owns the Ashita bridge (`src/workbench/runtime/live_client/*`, `addons/workbench_live/*.lua`, `native/ashita_workbench_probe`). No Toolkit doc mentions the headless client (grep of `docs/` found none), which is itself a documentation gap.

Toolkit state at audit: branch `feature/live-client-activity-feed` @ `94b2349b`; uncommitted: `M docs/shift_report.log`, untracked `data/assault/assault_reviews.db`, `data/root_archive/`, four `definitions.d/*.json`; 1 stash (`wip-before-main-sync-20261013`); worktrees `mt_domain`, `mt_pr1059`, `mt_research`, `mt_wt_ashita_plugin`. All left untouched. This research is committed from a separate worktree `<local>/mt_kuluu_research` (branch `research/kuluu-headless-comparison`, cut from `main` @ `f5a2cbd8`).

| Layer | Files (xiheadless-dsp) |
|---|---|
| Entry / lifecycle / reconnect loop | `Program.cs`, `BotHost.cs` (reconnect loop ~L72-179), `Brains/BotRunner.cs`, `Brains/BrainRegistry.cs` (reflection discovery by name) |
| Auth / lobby | `Net/LobbyClient.cs` (DSP plain-TCP 33-byte auth variant; 0x26 on view socket, 0xA1 on data socket) |
| Map session, crypto, framing | `Net/MapConnection.cs`, `Net/FfxiBlowfish.cs`, `Net/FfxiCompress.cs`, `Net/FfxiDecompress.cs`, `Net/SubPacket.cs` |
| Packet parsing | `Game/PacketParsers.cs`, `Game/ServerOpcodes.generated.cs` (LSB-derived; each opcode re-verified against DSP on demand), `Game/WorldState.cs` |
| Capabilities (interfaces in `Interfaces/`) | `Capabilities/{Perception,Events,Zoning,Inventory,Gear,Combat,Magic,Party,Chat,Shop,AuctionHouse,Bazaar,Crafting,Delivery,Quests,TradeNpc,JobChange,Lifecycle}.cs` |
| Navigation | `Navigation/{NavMesh,Navigator,NavLinks}.cs` (DotRecast `.nav`, `XIBOT_NAVMESH_DIR`) |
| Scenario / test layer | `Brains/ScenarioBrain.cs` (JSON steps + `expect` keys, writes `scenario_results.json`), `scenario_*.json`, `prep_*.py` (DB char staging), `run_*.sh/py` |
| Telemetry out | `Game/TelemetryWriter.cs` -> `<local>/FFXI-Tools\headless-research\telemetry\*.jsonl` |
| Brains | 45 files in `Brains/` (job brains, `DuoFightBrain`, `SurvivalGuideBrain`, `GmBrain`, ...) |
| Unit-test project | **None.** No `*.Tests` project; only scenario/brain-driven live tests |

Direct dependencies: DSP server (`<local DSP checkout>`, DB `dspdb_fresh`) for everything; retail client **not required**; Ashita not required; Toolkit only for telemetry display and for SQL-derived inputs (e.g. `sg_guides.json` built from `survival_guides_apply.sql`). Sibling research repos in `headless-research/`: `xiheadless` (upstream LSB), `GordianXI` (C# GUI client, protocol reference only), `headless-xi-rust` (search-server toy client).

## Matrix

| Capability | Our headless | Kuluu | Gap / advantage | Evidence |
|---|---|---|---|---|
| Authentication | **Verified working** (DSP 33-byte plain TCP, `result=0x01`) | Implemented, **BLOCKED vs DSP** (Json/TLS = LSB, Binary = 102-byte Horizon, PlayOnline) | Only ours speaks DSP. Kuluu `binary` sends 102 B; DSP ignores anything where `rdata.size()!=33` | `Net/LobbyClient.cs`; DSP `src/login/login_auth.cpp:82`; Kuluu `kuluu-session/src/auth_binary.rs` (`PAYLOAD_LEN=102`), `auth_client.rs` (`AuthFlavor`) |
| Character selection | Verified working | Implemented (LSB-oriented), untested vs DSP | Kuluu also creates/deletes chars (ours: DB prep) | sg.log `selected char id=21831`; `lobby_client.rs` `build_delete_char`, `CharCreateSpec` |
| Map-server connection | Verified working (multi-bot via `XI_BIND_LOCAL`) | Implemented (LSB), untested vs DSP | DSP finds char by source IP (`map.cpp:129`); Kuluu has no per-bot bind | FINDINGS.md L87; `map_client.rs` |
| Packet decoding | Partial (many opcodes "no field-parser yet") | Verified vs LSB (`ffxi-proto/src/decode`, layout tests) | Kuluu much broader, but LSB layouts | sg.log `[parse] ... no field-parser yet`; `ffxi-proto` |
| Packet encoding | Partial-to-working (pos, talk, event, magic, items, party, trade, AH) | Verified vs LSB (`ffxi-proto/src/map.rs`, `wire_translate.rs`) | Comparable breadth; Kuluu typed | `Capabilities/*.cs`; `wire_translate.rs` |
| Encryption | Verified working (Blowfish + md5 key rotation incl. DSP key16 rules) | Verified vs LSB | DSP key[16] quirk exists only in ours | FINDINGS L55; `ffxi-proto/src/{blowfish,md5}.rs` |
| Session recovery | Implemented, exercised (server-silent reconnect loop) | Verified by test vs LSB (supervisor backoff 1s to 60s, persisted goals) | Kuluu's goal persistence is the better design | `BotHost.cs` L116-179; `supervisor.rs`, `goal_store.rs`, `tests/disconnect_recovery.rs` |
| Position streaming | Verified (0x015; 2026-10-18 stationary-jitter fix for DSP entity resend) | Implemented (LSB) | DSP stationary-spawn quirk fixed only in ours | `MapConnection.BuildPos`; DSP 0x015 handler |
| Movement commands | Verified (MoveTo/Follow/Face) | Verified vs LSB (`path_to`, `follow`, `walk`) | Kuluu has a server-validated goal reactor | `Navigation/Navigator.cs`; `kuluu-mcp/src/main.rs` |
| Pathfinding | Verified (DotRecast per-zone `.nav`); Leujaoam multi-level routing **Missing** | Implemented (`ffxi-nav-recast`, `kuluu-nav`), needs retail DAT install | Different geometry source | leu logs "no navmesh for zone 79"; `kuluu-nav/` |
| Entity tracking | Partial (id/name/hpp/claim/pos; NPC names often blank) | Verified (`entity_stream.rs`, `scene://current`) | Kuluu richer | `Game/WorldState.cs`; `ffxi-proto/src/entity_stream.rs` |
| NPC interactions | Verified on DSP (Runic Seal 0x8C, Survival Guide 8500 x98, HP crystal) | Implemented + live tests vs LSB (events 503/531/568) | Equivalent; ours validated on DSP | `Capabilities/Events.cs`; `scenario_leujaoam_entry.json` 3/3; `sg_results.json`; `tests/event_*_live.rs` |
| Event scripting | Verified (ScenarioBrain `do`/`update`/`finish`/`expect`) | Partial (`ffxi-event` VM plays client cutscenes; agent mostly ends events) | Ours is test-oriented | `ScenarioBrain.cs`; `ffxi-event/src/vm` |
| Inventory management | Implemented (use/trade/shop/AH/bazaar/delivery) | Verified decode; `bank_when_full` goal | Comparable | `Capabilities/Inventory.cs`; `inventory.rs` |
| Wardrobes 1-8 | **Unknown** (no wardrobe handling found in `Capabilities/Inventory.cs` or `Game/`) | Verified decode (container capacity test incl. "Wardrobe2") | Kuluu ahead; confirm DSP container set first (DSP predates wardrobe 5-8) | grep; `ffxi-proto/src/decode/inventory.rs:251` |
| Equipment management | Implemented (`Gear.cs`, `EquipBrain`) | Unknown | - | `Capabilities/Gear.cs` |
| Combat actions | Verified (3-bot party: 5 kills, no deaths; spells, WS, JA) | Implemented (`cast`, `weaponskill`, `job_ability`, `engage`) | Equivalent; ours has role/party brains | trio logs; `DuoFightBrain.cs` |
| Zone transitions | Verified (GM `!pos`, zoneline, instance entry re-key) | Verified vs LSB (`zone_change` test) | Equivalent | `sg_results.json` 98/98 zone hops; `tests/zone_change.rs` |
| Mission automation | Partial (Leujaoam entry works; full run parked) | Missing (LLM playbooks only) | Ours | FINDINGS; `scenario_leujaoam_full.json` |
| Packet capture | Telemetry JSONL; raw capture is the Ashita/Toolkit side | Limited (`relay.rs`, `relay-probe` example) | Toolkit Ashita capture is unique | `capture_evidence.py`, `recording.py` |
| Protocol replay | Toolkit `replay.py` replays live-client observations | Missing | Ours (different layer) | `src/workbench/runtime/live_client/replay.py` |
| MCP integration | **Missing** (CLI + env + JSON scenario only) | Verified (rmcp server: tools, resources, `wait_for_event`) | Largest functional gap | `kuluu-mcp/src/main.rs` |
| Automated tests | Scenario live tests only, no unit tests | 222 + 89 test fns in session/reactor, live integration (self-skipping), conformance | Kuluu stronger | `session/tests.rs`, `reactor/tests.rs`, `kuluu-session/tests/*.rs` |
| Server-state validation | Verified (`prep_*.py` DB staging + expects) | Fixture-only (xidb) vs LSB | Ours validates against DSP DB | `prep_sg.py` |
| Feature Trace integration | Missing at headless layer (Toolkit has `feature_trace_*`; no link to scenario results) | Missing | Opportunity: emit scenario results as trace evidence | `src/workbench/core/services/feature_trace_*.py` |
| Multi-client testing | Verified (3-bot party, `XI_BIND_LOCAL`) | Unknown | Ours | `run_trio.sh` logs |

## Completeness verdict
Ours is a *functional DSP regression bot*: login, zone, fight, party, events and GM-assisted flows are demonstrated on the live DSP tree. Weak spots: packet-decoder breadth, no unit tests, no MCP or typed event contract, wardrobes unknown, not under version control.
