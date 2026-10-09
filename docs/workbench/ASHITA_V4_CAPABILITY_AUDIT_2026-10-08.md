# Ashita v4 capability audit for FFXI Mission Toolkit

Date: 2026-10-08  
Status: source-backed design research; not a claim of Windows runtime compatibility.  
Scope: FFXI Mission Toolkit, especially Live Client, Capture, Feature Trace, Zone Editor, DAT/Item tooling, Behavior Inspector and diagnostics.

## Executive decision

**Extend the existing read-only Ashita v4 Lua addon as the preferred, opt-in observation source.** Keep Toolkit's versioned telemetry/recording decoder and evidence correlation as the authoritative integration layer. Do not make the Toolkit depend on Ashita injection, copying its binary, or undocumented client offsets. A native Windows reader remains a separate option if APIs prove insufficient. Prioritize high-value, independently testable observation streams before any in-game control.

Ashita v4 offers (a) LuaJIT addons with event hooks and SDK-backed memory managers, (b) in-process entity/target/player/party/inventory/recast observations, (c) item/resource metadata and textures, (d) incoming/outgoing packet and chat hooks, and (e) lower-level C++ plugins and D3D integrations. These are *available surfaces*, not evidence that a particular FFXI build safely exposes each value. Prefer original Lua addon code and documented APIs, not copied framework internals.

## Evidence and toolkit baseline

- Ashita v4 public distribution and SDK: https://github.com/AshitaXI/Ashita-v4beta ; plugin interface https://github.com/AshitaXI/Ashita-v4beta/blob/main/plugins/sdk/Ashita.h
- Author-maintained v4 addon example, including coroutine/LuaJIT/FFI/event model: https://github.com/AshitaXI/example/blob/main/example.lua
- SDK binding test addon: https://github.com/AshitaXI/sdktest
- Core project docs: https://docs.ashitaxi.com/ ; features https://docs.ashitaxi.com/features/
- Real-world upstream examples: https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/equipmon/equipmon.lua ; https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/autorespond/autorespond.lua ; https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/blusets/blu.lua
- Toolkit docs already in repo: `docs/workbench/LIVE_CLIENT_BRIDGE.md`, `LIVE_CLIENT_NATIVE_RESEARCH.md`, `LIVE_CLIENT_REFERENCE_AUDIT.md`, `LIVE_CLIENT_WINDOWS_HANDOFF.md`; source `addons/workbench_live/`; capture archaeology `docs/workbench/CAPTURE_TOOL_ARCHAEOLOGY.md`.
- Existing Toolkit exporter is explicit-start, bounded read-only JSONL with player XYZ/heading/zone and selected target. Authorized operator supplied 121 observations over 120 seconds in zone 50; decoder/replay tests accepted them. The existing docs indicate later inventory experiments: verify current main and Windows evidence before assuming exact latest coverage. There is no warranted claim of live native process attachment, game writes, full map calibration or automatic multi-process discovery.
- This audit reviewed published pages and Toolkit GitHub files but **did not execute Ashita, inspect running process memory, verify version-specific field semantics, or run tests**. Historical v3 developer documentation is not v4 API authority; use v4 SDK/examples for callback names.

## Capability-to-Toolkit opportunity matrix

| Domain | Ashita v4 evidenced interface / technique | Toolkit application | Current gap and caveat | Priority |
| --- | --- | --- | --- | --- |
| Player telemetry | `GetMemoryManager` player/entity/party, entity `GetLocalPositionX/Y/Z`, `GetHeading`; `GetMemberZone(0)` | Live position, path recorder, Zone Editor preview, replay | Existing single-player exporter; raw axes/map transforms and timing need calibration | P0 extend |
| Nearby entity inventory | Entity interface exposes index-based `GetServerId`, `GetName`, `GetType`, `GetSpawnFlags`, `GetStatus`, `GetHPPercent`, positions | Live NPC/mob/player explorer, server SQL joins, placement candidates, spawning/despawning timeline | Bound enumeration, loaded/valid criteria, client slot vs server ID and type mapping require tests; don't treat all 0..N slots as entities | P0 |
| Target identity | `ITarget:GetTargetIndex` / `GetServerId`; entity target-related methods | target/subtarget distinctions, click-through Feature Trace lookup, target change events | Selected target already observed, role and server ID need explicit fields; indexes can be reused | P0 |
| Packet capture | Lua `packet_in`/`packet_out` hooks shown in released addons; SDK plugin hooks include original/modified buffer and chunk context | Canonical Capture ingest, opcode correlation, mission/event research, timeline with entities | Define byte-accurate raw/modified semantics and side effects; do not infer opcode meaning; high-volume logging needs caps | P0/P1 |
| Chat and command evidence | Incoming/outgoing text, command event interfaces | Dialogue/CSID correlation, user-marked probes, timing clues | Sensitive chat and credentials must be filtered; command handling observational only | P1 |
| Entity animations/appearance | SDK `GetAnimation`, `GetAnimationTime/Step/Play`, `GetModelTime/StartTime`, `GetLookHair/Head/Body/Hands/Legs/Feet/Main/Sub/Ranged`, `GetRace`, `GetEmoteId` | Model Viewer subanimation investigation, visual spawn metadata, animation provenance | These are SDK getters, not guaranteed meaningful at every sample; actor pointers/offsets should not be exported | P1 |
| Inventory & equipment | `IInventory:GetContainerItem`, `GetEquippedItem`, resource `GetItemById`; equipmon upstream | Item Editor/equipment icon cross-check, bag/equipped state diffs, action effects | Read-only; assess item extra-data privacy and server compatibility; equipment entry ≠ full item instance | P1 |
| Item image and resources | ResourceManager `GetItemById` yields metadata and item bitmap in equipmon; D3D8 texture load example | DAT icon audit, client/server resource drift, localization and item browser | Use item identifier + derived checksum/metadata before shipping binary bitmaps; extraction/redistribution rights | P1 |
| Party and jobs | `IParty`, `IPlayer` SDK managers | multi-actor party/zone context, job state and mission test metadata | Some state may be local or stale; profile explicit consent | P2 |
| Recasts / abilities | `IRecast`, player and recast manager; SDK test addon | behavior/effect inspector, live action timeline | Interpretability and authoritative server semantics require independent packet/script evidence | P2 |
| Mission/key item state | inventory/player resources plus raw packet evidence where actually observed | mission progression triage and quest validation | No claim of direct stable mission-flag/key-item API without v4 per-method inspection; avoid speculative decoding | Research |
| Real-time in-game overlay | D3D device/resource surfaces and addon UI; upstream equipmon UI | optional client-local inspector / capture status | Toolkit web UI is preferable for core UX; overlays are nonessential and can disrupt graphics | P3 |
| Multi-client | each separately injected addon + session/exporter identity | compare client positions/targets/event observations | no OS discovery implied; require unique source IDs, client lifetime, clock correlation | P1 |
| Memory patching / injection | SDK C++ plugin + LuaJIT FFI can access lower-level memory | potential future developer-only diagnostics | high breakage and integrity risk; **exclude from observation phase**; do not export addresses or transplant offsets | Deferred |
| Spatial writes / warp / speed / clipping | Not established as safe published Ashita v4 API contract by sources here | possible separate authorized lab adapter | no Toolkit write implementation proven; must be separate from read-only exporter and gated to authorized environments | Out of scope |

## Detailed high-value investigations

### A. Comprehensive entity snapshots
Implement a **separate opt-in entity enumeration module** integrated through the current exporter. Record selected observations at low bounded rates, not an unthrottled full frame dump. Establish supported enumeration size/validity via current v4 headers/annotations and an authorized live trial. Suggested fields: schema version, source/instance ID, observation timestamp, zone and unknown instance hint, index, observed server ID (nullable), name (nullable), raw type, spawn/status, HP%, XYZ, heading, observed-target role, flags, and validity/rejection reason. Preserve *raw type code* until a verified interpretation table exists. Never assume the client memory slot is a server SQL ID. Entity absence needs an explicit distinction between not observed, unloaded and despawned; never synthesize a death/despawn event just because an entry vanished once.

Use the in-memory observation for Zone Editor overlays and compare IDs against DSP/Topaz/LSB server DB records with provenance. Require zone and instance compatibility before highlighting an entity match. This likely delivers the largest improvement to Feature Trace because observed target IDs can open server Lua, spawn rows, client DAT, wiki and packet evidence together.

### B. Packet capture as a first-class Ashita source
Use Ashita v4's `packet_in` and `packet_out` callbacks **passively**; upstream examples demonstrate both. Canonical event fields: source ID, monotonically increasing local sequence, wall clock and monotonic-tick where practical, inbound/outbound, packet ID, length, raw bytes as base64/hex, hook stage, injected/blocked indicators where exposed, optional chunk affiliation. The C++ SDK exposes chunk buffers and original/modified data, but a Lua event's precise properties should be confirmed from the *v4* sample/source before making a schema promise. Preserve original packet, never emit modified bytes as wire truth; client hook captures are not automatically equivalent to PCAP TCP/UDP streams. Store selected IDs and configurable sampling/size limits, cap disk, redact sensitive packets and avoid chat logging by default. Incorporate into existing Capture canonical pipeline rather than introduce a parallel decoder.

### C. Event/mission/behavior correlation
Create a common time-indexed evidence join keyed by (capture source, client/session, zone, time window, target server ID and raw opcode), retaining uncertainty. UI should show causal hypotheses separately from verified links. User workflows: target NPC -> press interact -> log packet/chat/cutscene clues -> correlate with LSB/DSP/Topaz Lua `onTrigger`/`onEventFinish` and wiki page -> compare server state and live observation. Distinguish a packet's unknown decoded semantics from a Lua/SQL code reference. Build one end-to-end known-event test case before expanding to all missions.

### D. Animation and client model research
Inspect entity animation fields plus appearance `GetLook*` and emote values; sample changes alongside packet events and timestamped video/CSID where provided. Correlate observed animation identifiers with model DAT animations but do **not** assume one numerical ID is directly transferable between client memory and DAT model indices. Store raw values, observed timing and build metadata. This could support subanimation naming, equip/render debugging, and combat/emote provenance.

### E. Inventory and resource reconciliation
Collect only opted-in compact item state (container ID, slot, item ID, count and equip slot), retaining sensitive/variable instance data separately if required. Compare against current server item DB and client resource item metadata, including icon identifiers and stacks. Upstream `equipmon.lua` demonstrates inventory and `GetItemById`/Bitmap access; this is good reference evidence, not license to redistribute game graphics. Expose drift reports in existing Item/Equipment editor, not live mutation.

### F. Time, transport, provenance and health
Current one-second JSONL exporter is a valuable baseline. Extend with a format-versioned stream type, separate source/recording/session identities, per-stream sequence, source framework version, user-supplied game build and explicit version-verification status, safe timestamps, truncated-frame marker, dropped event count, and stop reason. Clock align by recorded host UTC plus monotonic progression; document uncertainty when joining with packet/file/video/server clocks. Begin with local bounded JSONL; then an explicit loopback-only read-only transport if polling latency becomes limiting. No implicit network service, broad interface binding, or arbitrary remote client control. Ensure source unload, zoning, logout and client replacement force new identity checks.

## Integration architecture

```text
Authorized FFXI client + Ashita v4
  ├── workbench_live Ashita Lua producer (opt-in, observation-only)
  │   ├── player / target / entity sampler
  │   ├── optional packet event sampler
  │   ├── optional animation / item observation sampler
  │   └── strict bounded JSONL (later explicit local transport)
  ↓
Toolkit file feed / recording validation
  ↓
Canonical telemetry + packet + entity evidence stores
  ├── Client > Live Client replay/compare
  ├── Capture > Packet viewer / Event / CSID / cross-capture search
  ├── Feature Trace > live target -> server Lua/SQL/client/wiki
  ├── Zone Editor > position/path/entity read-only overlays and proposals
  ├── DAT / Model Viewer > appearance/animation correlation
  └── Item / Equipment > icons/inventory drift reports
```

The stream should remain usable offline, under cloud CI and without Ashita installed on the server that hosts Toolkit. A Windower producer can share schema without attempting to match unsupported fields.

## Delivery roadmap — isolated, testable slices

1. **P0 contract inventory (docs/tests only).** Diff latest `main` against this audit, extract exact `workbench_live` files and v4 headers, inventory exporter capabilities including any recently added entity sampling, and publish field-level gap matrix. No GUI or Live Client branch modifications until reconciliation.
2. **P0 entity snapshot 2.0.** Bounded source enumeration, explicit original index + server ID + raw flags, player and target labels, valid/stale state. Synthetic Lua SDK tests + malformed feed tests + one Windows test. Coordinate ownership with Live Client agent.
3. **P0 hook packet feasibility.** Experimental separate opt-in read-only packet file stream; choose a few known event IDs, capture original direction/bytes/time, show decoded/unknown status without mutation; comparison against existing PacketViewer/PCAP logs.
4. **P1 Feature Trace evidence adapter.** Normalize client observation -> entity candidate query, link only source-confirmed IDs; no edits to wiki agent's data ingestion/schema.
5. **P1 animation study.** Watch one NPC/mob/player while triggering known emote/battle events; record animation fields and build evidence map; compare DAT model catalogue.
6. **P1 resource/inventory diagnostic.** Enumerate read-only item/equipment metadata and compare IDs/icons with Toolkit icon pipeline.
7. **P1 multi-client isolation and clock sync.** Distinct source IDs, zone changes, version identity and export isolation, dropped-sample reporting and replay tests.
8. **P2 client-local UX.** Optional capture indicators and local overlay only if web Live Client cannot meet need; assess performance and D3D hook conflicts.
9. **P2 advanced state research.** Party/recasts/key items/quest flags only after verifying the exact v4 API and suitable privacy minimization.

For each slice: independent fixtures, recording compatibility, validation failures/stop reasons, source attribution, resource/time caps, API-version guard, Windows smoke report, and explicit rollback. Merge only evidence-backed work.

## Validation checklist for the authorized Windows system

- Capture actual Ashita version, addon revision, game module version/hash metadata (never upload executable by default), OS and server family.
- Start/restart/unload from an opt-in command; verify nothing captures before start.
- Standing still, moving, rotating, stairs, zoning, logging out and reconnecting: measure position axes, heading units, sample timestamps and stale/disconnect behavior.
- Target a known NPC/mob/player, untarget, retarget, watch slot reuse; compare names/server IDs with a separate reliable client/server observation.
- Bound entity enumeration and measure frame impact over a populated zone; check absent/invalid/duplicate/index-zero entries.
- For packet experiments, compare hook-observed byte counts/IDs with a known Capture source; test chat/privacy redaction, injected/blocked labels and chunk assumptions.
- Capture a known NPC interaction and correlate target + outgoing and incoming packets + Lua event + dialogue; unknown interpretations stay unknown.
- Record animation before/during/after a known action; validate actual meaning of all observed getters before naming them.
- Validate two instances independently, including same character or same client ID accident.
- Verify crash/stop/low-disk/oversized file handling, file permissions, source update, and backward-compatible replay.
- Record **expected vs observed**, each field's verified/uncertain/unsupported status and provenance. Never promote a synthetic test pass into runtime verification.

## Risk, legal and scope guardrails

- **Version/ABI:** v4 public beta SDK interfaces and Lua event argument names can change; pin inspected references and gate compatibility. The SDK interface version appearing in a current source header is not the same as a verified user installation.
- **Licensing:** Ashita v4 repository distinguishes GPLv3 application from LGPLv3 SDK. Upstream bundled addon files may be GPL; use their code for reference and implement original Toolkit Lua, with attribution/licensing review if actual code copied. Do not bundle Ashita binaries or extracted game assets in Toolkit.
- **Performance:** per-frame entity/packet collection can create heavy IO; bounded time/bytes/queues and one-second or event-triggered sampling are safer defaults.
- **Data minimization:** player/party names, chat and game credentials may be sensitive. Default to local-only output, redact chat/content unless explicitly selected, provide capture start/stop and deletion controls.
- **Untrusted source:** exporter may run on unauthorized or modified environments; captured frames are evidence with provenance, not proof of server truth. Server-side SQL/Lua and packet streams remain independent evidence.
- **Game mutation:** packet injection, blocking, memory modifications, process patching, stealth/anti-detection, clip/warp/speed are deliberately excluded from this observation audit. A future developer-only control subsystem requires separate review, version verification, authorization and rollback.
- **No invented spatial truth:** never transform raw client XYZ or assume instance/map resolution without calibration.

## Recommended ownership boundaries

- This research document is isolated under `docs/workbench/` to avoid colliding with active Wiki and Live Client agents.
- Live Client agent owns `addons/workbench_live/`, `src/workbench/runtime/live_client/` and related tests; incorporate this as design input after branch reconciliation.
- Wiki agent owns wiki ingestion, translation, formatting and multilingual linking; only integrate evidence references through an agreed read-only contract.
- Capture/Feature Trace improvements can proceed separately once schema ownership and shared router changes are coordinated.
- Do not edit `ROADMAP_CURRENT.md`, shared GUI routes, current exporter or wiki files from a research-only branch without reconciling active work.

## Research confidence summary

**Verified in published upstream source:** plugin/SDK interface, Lua addon example, packet hooks in distributed addons, entity/target getters, inventory and resource bitmap example, LuaJIT/FFI execution mode.  
**Verified by prior Toolkit documentation/operator evidence:** a bounded read-only Ashita player/target exporter and a limited successful real-game recording accepted by Toolkit's decoder.  
**Not verified in this audit:** current exact main branch/exporter coverage beyond checked docs, live full-entity enumeration, packet logger operating on this client, animation semantics, runtime resource extraction fidelity, zone map transforms, client write/control capability or stability under load.

## Source index

1. Ashita v4 releases: https://github.com/AshitaXI/Ashita-v4beta
2. SDK headers: https://github.com/AshitaXI/Ashita-v4beta/blob/main/plugins/sdk/Ashita.h
3. v4 Lua example: https://github.com/AshitaXI/example/blob/main/example.lua
4. SDK test addon: https://github.com/AshitaXI/sdktest
5. Official documentation: https://docs.ashitaxi.com/
6. Upstream equipmon: https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/equipmon/equipmon.lua
7. Upstream packet example: https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/autorespond/autorespond.lua
8. Upstream BLU state example: https://github.com/AshitaXI/Ashita-v4beta/blob/main/addons/blusets/blu.lua
9. Toolkit base evidence: `docs/workbench/LIVE_CLIENT_REFERENCE_AUDIT.md`
10. Toolkit exporter test plan: `addons/workbench_live/README.md`
