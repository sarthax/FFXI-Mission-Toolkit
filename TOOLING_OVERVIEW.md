# FFXI-Tools Complete Inventory

Full inventory of the FFXI research/tooling pipeline as of 2026-08-31: what existed before, what changed this session, and what was newly built. All paths relative to `D:/Claude/FFXI-Tools/` unless noted. "Ground truth" tools (real client dats, real Topaz source) are called out explicitly vs. reference-only sources (wikis, external retail dumps).

---

## Part A — Foundational extraction tools (pre-existing, unchanged unless noted)

### `dat-extractor/`
Standalone .NET console app, ported out of POLUtils, for reading FFXI `.DAT` files directly. Two real jobs:
- `dat-extractor <path.dat> [out.json]` — extract one dialog-table DAT to JSON.
- `dat-extractor --scan <romRoot> [--min N] [--contains "text"]` — scan a whole ROM tree for dialog tables matching text.
- `dat-extractor --resolve <ffxiPath> <fileId> [<fileId> ...]` — **the one used everywhere else in this pipeline**: real FTABLE.DAT/VTABLE.DAT-based file-id → physical ROM path resolution, batched. Ground truth, not a guess.

**Used by:** `mission_toolkit.py`, `model_schedule_dump.py`, `build_database.py --zones`.

### `xi-tinkerer-py/`
PyO3 (Rust→Python) bindings onto `xi-tinkerer`'s `dats` crate. Exposes native, in-process parsers: `parse_menu_table`, `parse_dmsg_table`, `parse_dialog`, `parse_entity_names`, `parse_events`, `parse_item_info`, `parse_status_info`, `parse_xistring_table`, `parse_auto_translate`, `parse_furniture_data`.

**Changed this session:** `mission_toolkit.py` was rewired from shelling out to a separately-built `xi-tinkerer-cli.exe` + YAML round-trip, to calling these native functions directly. This eliminated a real bug class (PyYAML auto-parsing unquoted hex `byte_code` as a Python int instead of a string).

### `xi-events-py/`
Real CFG + branch-recovery decompiler: FFXI event bytecode → readable Lua pseudocode. Its own "front door" (`Dataset.from_dist(...)`) expects a released `FFXI-Resources` ndjson dataset.

**Added this session:** `decompile_from_mission_toolkit.py` — a bridge script wiring `mission_toolkit.py`'s own `events.yml`/`dialog.yml` export directly into `xi_events.Fixture`/`decompile()`, so decompilation works against our own zone pulls without needing the separate FFXI-Resources dataset. Verified correct against event 661 (Nafiwaa) both before and after `mission_toolkit.py`'s native rewrite (it already used structural `yaml.safe_load()`, so the rewrite didn't break it — only its docstring needed updating to describe the new pipeline).

### `FFXI-EventsDump/`
Pre-generated, already-decoded dump of **every** event in the game (based on atom0s' XiEvents opcode parsers). Per zone: `<entity_id> - <name>.md` (full opcode disassembly, human-readable operands), `Zone Events.md` (every event id/entrypoint/size in one table — the fast "who owns this csid" answer), `strings.txt` (dialogue text, same numbering as `mission_toolkit.py`'s `dialog.yml`).

**Unchanged.** First stop for any event/dialogue question — no pipeline to run.

### `XiEvents/`
Local opcode reference + tooling:
- `opcode_table.json` / `opcode_docs.json` — 218 documented real opcodes (parsed from atom0s' `OpCodes/*.md` via `decode_opcode_docs.py`).
- `smart_disassemble.py` — semantic disassembler reading `mission_toolkit.py`'s `events.yml`: resolves message refs, menu opcodes (`0x24`/`0x25`), condition types (`0x02`'s 11 real branch cases), `getworkofs` (Work_Zone/WorkLocal/References resolution).

**Changed this session:** `extract_event()` was rewritten from regex-on-raw-YAML-text to real `yaml.safe_load()` + dict traversal, after `mission_toolkit.py`'s native rewrite changed field order/indentation in the output and silently broke the old regex (no error, no output — just nothing matched). Verified against both a real multi-command event (661) and a known stub case (5030).

### Packetlyzer (`Packetlyzer/`)
Third-party (Exolis) real-time packet capture/decode tool: Windower/Ashita addon + Python GUI, live 2nd-screen packet viewer with byte tracking, opcode filtering, and built-in DAT-file text resolution for things like campaign status updates.

**Unchanged, evaluated not adopted into the pipeline** — its DB-driven NPC-lookup is hardcoded to LSB's schema (author's own README notes this), and its role (live capture during actual play) doesn't overlap with this pipeline's offline/batch research tools. Kept for when live-capture debugging is needed.

### `Ashita`, `LandSandBoat`, `Lua` (Windower/Lua clone)
Reference-only client-side/server-side source trees, not standalone tools. Used for cross-checking packet field layouts (`Lua/addons/libs/packets/fields.lua` — this is where the real `0x00E` entity-update packet layout with the `Model`/`Name` fields came from) and porting quest logic (LandSandBoat reference scripts, e.g. the Promotion: Lance Corporal port).

---

## Part B — Zone/mission data pipeline

### `mission_toolkit.py`
One-stop zone/mission puller: given a Topaz zone name/id, resolves geometry dat id (via AltanaViewer's zone CSV), resolves events/dialog/entities dat ids to real ROM paths (`dat-extractor --resolve`), parses them natively (`xi-tinkerer-py`), writes `events.yml`/`dialog.yml`/`entities.yml` to an output folder.

```bash
python mission_toolkit.py Aht_Urhgan_Whitegate --out-dir mission_reports_v2
```

**Rewritten this session** (see Part A, `xi-tinkerer-py`) — output format/shape is unchanged, only the internal extraction mechanism. Fixed a real double-path-prepend bug during the rewrite (`dat-extractor --resolve` already returns an absolute path).

### `build_database.py` → `ffxi_zone_database.db`
Consolidates every source above into one queryable SQLite DB.

| Table | Source | Purpose |
|---|---|---|
| `zones` | `zone.lua` + AltanaViewer CSV | zoneid ↔ name ↔ geometry dat id |
| `door_props`, `elevators`, `zone_lines` | `FFXI-DATS` JSON | real prop/elevator/zoneline positions, all zones |
| `entities` | `FFXI-DATS/Entities/*.json` | external (possibly different client version) entity id/name per zone |
| `entities_ours` | live `xi-tinkerer` pull, per-zone | OUR OWN client's entity id/name, ground truth |
| `id_drift` | computed | zoneid+server_id pairs where `entities` and `entities_ours` disagree on name |
| `events` / `events_disasm_flags` | live `xi-tinkerer` pull, per-zone | event bytecode + flagged noteworthy opcodes |
| `items_external` / `items_ours` | FFXI-Resources vs `item_basic.sql` | **new this session** |
| `keyitems_external` / `keyitems_ours` | FFXI-Resources vs `keyitems.lua` | **new this session** |

```bash
python build_database.py                  # reload all globally-available sources
python build_database.py --zones 66 68    # also pull live events/entities for specific zones (slow)
```

### NPCLogger cross-reference pipeline (`D:/Claude/DSP-Topaz Information/npclogger_crossref/`)
Three-stage pipeline (`scripts/crossref.py` → `step2_mine.py` → `step3_crossref.py`) cross-referencing real Assault capture data (mined from every NPCLogger `.db` under `D:\Claude\assault_captures\`) against Topaz's own SQL/Lua, to find entities that exist in real captures but aren't fully wired (missing `npc_list`/`mob_spawn_points` row, missing `instance_entities` registration, missing an `IDs.lua` reference).

**Unchanged this session.** As of last run: 371 real fixes already applied across 20+ missions; 222 entities still have no SQL row at all (tiered by confidence in `TODO.md`); 27 name anomalies and 94 cosmetic missing-Lua-reference entries catalogued but not yet reviewed. Re-run after any further SQL/Lua changes for a fresh findings CSV. **Not yet merged with `build_database.py`/`entities_ours`** — same underlying ground-truth principle, separate pipeline, a real future consolidation opportunity.

### Older single-purpose SQL-fix scripts
- `pull_mob_positions.py` — finds real spawn positions for zero-position `mob_spawn_points` rows by matching a capture's PathLog CSVs by mob id.
- `fix_zone_door_props.py` — cross-references `npc_list.sql`'s anonymous prop rows against `FFXI-DATS`' real door/object positions via nearest-neighbor XZ match, restricted to ids `FFXI-DATS` confirms belong to that zone; dry-run by default, `--apply` writes the fix.
- `audit_dialog_drift.py` — cross-references each zone's `IDs.lua` `text` table's inline "expected real text" comments against that zone's real dialog table (from our own client), flagging drift — the same id-offset pattern documented in `topaz_client_id_offset` memory.

**Unchanged this session.** All three follow the same "verify against our own client/capture, never trust an external id" discipline as everything built this session.

---

## Part C — Item/key-item/wiki research (new this session)

### `id_bridge.py`
LSB/retail → Topaz ID bridge for items and key items, matching by **normalized name**, not by id (ids drift, names mostly don't).

```bash
python id_bridge.py item "Chocobo Bedding"
python id_bridge.py keyitem --id 794
python id_bridge.py drift-report keyitem --limit 50
```

**Real finding:** of unambiguous 1:1 name matches, **0 of 14,535 items** have a drifted id (LSB item ids are safe to trust once uniquely named), but **2,910 of 3,242 key items (90%)** have a different id between LSB and Topaz. Never trust an LSB key item id without running it through this tool first.

### `wiki_lookup.py`
Offline query tool over a downloaded BG Wiki dump (`ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz`).

```bash
python wiki_lookup.py title "Promotion: Lance Corporal"
python wiki_lookup.py category Assault --zone "Ilrusi"
```

**Explicit framing:** reference only, not source of truth — player-written, can be stale or wrong for Topaz's era. Orient with it, verify anything load-bearing against Topaz's own dats/SQL/Lua.

### `item_id_drift_report.txt`
Saved full output of `id_bridge.py drift-report item` — the "0 drifted items, 90% drifted key items" finding, with the ambiguous-name and unmatched-name counts, kept for quick reference without re-running the query.

---

## Part D — Model, animation, and look-string ground truth (new this session)

### `xi-model-viewer/` (cloned this session, third-party by vekien)
Full Tauri/WebGL2 FFXI asset browser: zone geometry (weather/time-of-day), NPC/monster/PC model viewer with animation playback and bone-hierarchy inspection, character composer, spell/ability VFX playback, texture/music/SFX browsers, and an FTABLE/VTABLE file-id browser. Its `ui/js/dat.js` (DAT section walker, skeleton/mesh/texture/animation parsers) and `ui/js/dat/modelids.js` (gear/entity model-id resolution tables) are the real, ported-from-`xi-tools` parsing logic this session mined for ground truth — not the Tauri app itself.

**Potential role:** a real AltanaViewer replacement for interactive model/zone browsing — not yet evaluated head-to-head for that role.

### `model_schedule_dump.py`
Pure-Python port of `xi-model-viewer`'s `walkSections`/`parseRoutine`/`matchAnimRef`. Resolves a file id, monster/NPC model id (`98239 + model_id`), or direct ROM path to a real DAT, then dumps every `0x07` schedule's animation commands with absolute start times and resolved clip ids.

```bash
python model_schedule_dump.py --dat "ROM/27/82.DAT"     # verified: 67 real schedules
python model_schedule_dump.py --model-id 356
```

**Closes a real gap:** decompiled event calls like `loadExtSchedulerMain` pass numeric animation-tag arguments with no global lookup table — tags are per-model wildcard clip refs, only resolvable against the specific entity's own model DAT. This script does that resolution.

### `mob_look_decode.py`
Decodes a Topaz `mob_pools.modelid`/`npc_list` look blob using Topaz's own real `look_t` struct (`C:\topaz\src\common\mmo.h`) and `MODELTYPE` enum (`entity_update.h`) — not inferred, read directly from source.

```bash
python mob_look_decode.py --poolid 649     # Carrion_Crab -> MODEL_STANDARD, flat modelid 356
python mob_look_decode.py --poolid 1       # 1st_Gold_Musketeer -> MODEL_EQUIPED, HumeFemale, 8 gear ids
```

**Real, confirmed finding:** flat-model monsters (`MODEL_STANDARD`/`AUTOMATON`/`UNK_5`) resolve to exactly one DAT. Humanoid-look entities (`MODEL_EQUIPED`/`CHOCOBO`) have **no single DAT at all** — the client composites a base race-skeleton DAT with one DAT per equipped gear slot, live, the same mechanism as `xi-model-viewer`'s own PC character composer.

**Honestly unresolved, not papered over:** the `98239` flat-model-id offset (sourced from real `xi-model-viewer` code) hasn't been confirmed to resolve against Topaz's actual client for any real monster id tried — `dat-extractor --resolve` returned "not found" for every one, possibly a real sparse FTABLE gap rather than a wrong offset. The `MODEL_EQUIPED` gear-slot numbers also don't match `xi-model-viewer`'s own PC `GEAR_TABLES` ranges. Both need a live-capture cross-check before further automation is built on top.

---

## Part E — Other asset tools (pre-existing, unchanged)

### `ResourceBuilder/`
Parses Windower `ResourceExtractor` output and writes edited resources back into real FFXI DAT files (adjust or add, never removes). Used once, for items only — not yet applied to anything in the active pipeline.

### `UpdateExtractor/`
Takes `POLUtils`' `MassExtractor` data dump and sanitizes/applies it to a LandSandBoat-style server install (version strings, item/keyitem/status/entity/title/zone-text updates). Built for LSB, not directly used against Topaz's schema — reference for what a "diff two client versions" tool looks like.

### `AltanaViewer/`
Third-party 3D model/asset viewer (characters, monsters, equipment, animations, artwork, some music/VFX). Long-standing source for `mission_toolkit.py`'s zone-geometry dat-id CSV (`ffxi/reference/AltanaViewer_zones.csv`). Possibly superseded by `xi-model-viewer` for interactive browsing — not yet evaluated.

### `Resources`, `FFXIDat`, `MassExtractor_output`, `ResourceExtractor`
Supporting/raw output directories from the above tools' extraction runs — not independently invoked, feed the tools above.

---

## Decision order for a new research question

1. **`FFXI-EventsDump/dumps/<zone>/`** — pre-generated, decoded, check first, no pipeline to run.
2. **`xi-events-py`** (via `decompile_from_mission_toolkit.py`) — need actual Lua-like pseudocode for one specific event.
3. **`mission_toolkit.py`** — geometry/entity data, or an event `FFXI-EventsDump` doesn't cover clearly.
4. **NPCLogger crossref pipeline** — is a capture-observed entity actually wired into Topaz's SQL/Lua?
5. **`id_bridge.py`** — before trusting ANY LSB item/key item id against Topaz.
6. **`wiki_lookup.py`** — quest/mission orientation, always followed by a Topaz-side verification of anything load-bearing.
7. **`model_schedule_dump.py` + `mob_look_decode.py`** — when animation/model behavior is in question.
8. **Packetlyzer** — when the question requires live, real-time capture rather than offline batch analysis.

## Standing rule underneath all of it

Never trust an externally-sourced numeric ID, offset, or struct-layout guess without checking it against Topaz's own SQL/Lua/C++ source, a real capture, or `dat-extractor`'s ground truth. Every tool above either confirms this the hard way (2,910 drifted key items, 371 real SQL/Lua gaps found by NPCLogger crossref) or is honest about what it couldn't yet confirm (the model-id offset, the gear-slot numbering) rather than presenting a guess as settled.
