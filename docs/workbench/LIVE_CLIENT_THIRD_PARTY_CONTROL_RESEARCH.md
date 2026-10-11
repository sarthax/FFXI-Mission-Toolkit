# FFXI Live Client — Third-Party Control and Capture Reference Audit

**Recorded:** 2026-10-11  
**Status:** Research backlog; not implementation authorization  
**Project:** FFXI Mission Toolkit — Live Client, Captures, Entity, Zone Editor, Feature Trace

## Decision and current boundary

Continue the existing Ashita v4 Live Client integration rather than introducing a second native hook prematurely. The authenticated **read-only** Toolkit ↔ client round trip was confirmed in the Windows environment. A native Ashita v4-Beta plugin has also successfully loaded and reported changing player XYZ positions; neither test demonstrates the ability to move the player programmatically. Keep the existing bridge and native plugin as the preferred integration foundations, and validate command acknowledgment, native-versus-Lua telemetry agreement, and server-observed movement before adopting another control stack.

Distinguish four capabilities throughout: **observation**, **client command**, **client-directed movement**, and **server-authoritative relocation**. Evidence for one is not evidence for another. Coordinate-directed autofollow does not establish arbitrary teleportation or navmesh bypass.

## Verified progress (updated 2026-10-11)

| Area | Evidence and implementation | Remaining limitation |
|---|---|---|
| Direct Live Bridge | Windows `/wblive bridge ping` returned authenticated read-only round-trip confirmation; PRs #961–#964 introduced simulated movement guards, loopback round-trip and bounded session-scoped capability-probe delivery | No movement command execution or server-confirmed position update |
| Installer | PR #965 merged a primary backup-and-replace workflow for installed Ashita addon files, retaining private settings | Operator should confirm replacement on the actual Windows installation; prior manual-deletion problem is addressed in code, not independently validated as resolved |
| Ashita Lua movement API audit | Windows `/wblive movement audit` reported warp pointer and position setter not exposed; a candidate outgoing-packet API was present but unverified; PR #966 merged | Does not rule out other Lua methods or prove packet-driven movement |
| Native Ashita plugin | Windows Ashita v4.05 Beta x86 plugin compiled, loaded, responded to `/wbprobe`, and unloaded; PR #969 merged | No movement writes; the Windows SDK differs from some public SDK interfaces |
| Native XYZ readback | Windows `/wbprobe position` reported zone **98**, entity index **1024**, and changing XYZ across multiple samples | Independent server acceptance and native-versus-Lua agreement still require testing |
| SDK compatibility | Windows build required C++20 (`std::ranges` in SDK headers) and bounded entity-map scanning by server ID (the Beta SDK lacked `IResourceManager::GetEntityIndexById`) | Avoid assuming public header interfaces match this installed Beta SDK |
| Position comparison | PR #969 merged a read-only coordinate comparison service with zone, sample-age and distance guards | Library/service implemented, not yet exposed in the dashboard or validated against paired Windows samples |

**Current delivery boundary:** Native read access and authenticated transport are established. Actual Toolkit-controlled player movement, direct XYZ writing, packet injection, stop execution, and **server-authoritative relocation** remain unimplemented or unverified. The third-party projects below are research references, not newly integrated dependencies.

**Next priorities:** (1) Compare synchronized native and Live Client XYZ; (2) inspect the installed native SDK for legitimate position setters and movement interfaces; (3) prototype an explicitly armed, bounded test only on the authorized DSP/Topaz development environment, with cancel/stop and server-side verification; (4) revisit Cure Please event, entity, and capture features after the movement test. Keep the Toolkit roadmap and help pages synchronized as each feature is actually delivered.

## Reference projects

| Reference | Source | Research value | Integration caveat |
|---|---|---|---|
| Cure Please | https://github.com/DanielHazzard/Cure-Please | Event bridge, cast/buff/status events, multi-process state, targeting and coordinate-directed autofollow | C# companion uses EliteMMO/EliteAPI; native dependency and its license must be checked |
| Cure Please Ashita addon | https://github.com/DanielHazzard/Cure-Please/tree/master/AshitaAddon | Packet/event forwarding into companion process | Review Ashita v4 compatibility; do not assume drop-in support |
| Cure Please Windower addon | https://github.com/DanielHazzard/Cure-Please/tree/master/WindowerAddon | Alternative event adapter and normalized event semantics | Windower native runtime is a separate dependency |
| Project Tako / Clipper | https://github.com/ProjectTako/ProjectTako and https://github.com/ProjectTako/Clipper | Movement behavior, spatial inspection, menu/NPC testing reference | Verify implementation, license, and binary dependencies before reuse |
| Project Tako addons | https://github.com/ProjectTako/ffxi-addons | ScanZone/entity observations, menu and NPC interaction research | Verify repository contents and addon compatibility at implementation time |
| Ashita v4 SDK example | https://github.com/AshitaXI/ExamplePlugin | Candidate C++ native plugin interface for player/entity/target/autofollow | SDK visibility does not imply the underlying Ashita hook is open source |
| Ashita third-party source | https://github.com/AshitaXI/thirdparty-src | C++ implementation patterns | Per-component license and API version must be audited |
| Windower Lua | https://github.com/Windower/Lua | Addon event, packet, equipment and action patterns | Lua repository is not a full native hook implementation |
| Community addons | https://github.com/Icydeath/ffxi-addons and https://github.com/Lygre/addons | Follow, targeting, action/recast, packet and state patterns | Candidate references only; verify exact addon paths and licensing |

### Cure Please evidence to revisit

- Main app: https://github.com/DanielHazzard/Cure-Please/blob/master/Form1.cs
- Ashita addon: https://github.com/DanielHazzard/Cure-Please/blob/master/AshitaAddon/CurePlease_Addon/CurePlease_Addon.lua
- Windower addon: https://github.com/DanielHazzard/Cure-Please/blob/master/WindowerAddon/CurePlease_Addon/CurePlease_Addon.lua
- Previous source inspection found `EliteAPI`-based player/entity XYZ reads, target management, and `AutoFollow.SetAutoFollowCoords(dX,dY,dZ)` / `IsAutoFollowing` in the companion app. The addons reportedly relay game-derived events over loopback UDP (default 127.0.0.1:19769). Recheck exact APIs, behavior, and versions before implementation.

## Reusable use-case backlog

| Rank | Capability | Toolkit integration | Acceptance evidence |
|---|---|---|---|
| 1 | Event-driven buff/status/cast/interrupt reporting | Live Client + Capture event schema | Timestamped event with client ID, source, opcode/provenance where available; correct transitions |
| 2 | Entity discovery / ScanZone-style observation | Entity Browser, Zone Editor, 2D/3D viewers, Feature Trace | Entity ID/index, zone, XYZ, type, first/last seen, source, confidence; no invented identities |
| 3 | Configurable high-frequency player telemetry | Live Client and 2D/3D viewers | Measured latency, update rate, drop/stale indicators, smooth viewer position |
| 4 | Multi-client isolation and coordination | Live Client session registry | Independent identity, zone, timestamps, commands and disconnect recovery |
| 5 | Structured command and target control | Live Client, Entity Browser | Explicit acknowledgments, timeout/failure semantics, target restoration and audit log |
| 6 | Packet-triggered research capture | Capture, Packet Viewer, Evidence Search | Correlated packet/event stream around NPC, CSID, battle, and zoning events |
| 7 | Action/recast/equipment/inventory observation | Item, AH, Character and combat research | Event/state correlation with authoritative IDs and source references |
| 8 | NPC/menu interaction replay | Missions, Events/CSID, Feature Trace | Reproducible private-server interaction with packet and Lua evidence |
| 9 | Coordinate-directed follow | Live Client spatial controls | Controlled movement test with explicit safety gate and server-observed result |

## Proposed common event contract

Fields to evaluate: `schema_version`, `client_id`, `session_id`, `source_adapter`, `source_timestamp`, `received_timestamp`, `sequence`, `zone_id`, `entity_id`, `event_family`, `event_type`, `payload`, `raw_reference`, `confidence`, `drop_count`. Preserve raw packet/event evidence where permitted, and label derived values distinctly from observed values.

Separate **frequent position/heading/target telemetry** from **event-triggered status, action, NPC and packet streams**. Include rate configuration, stale-data detection, queue/backpressure and per-client isolation. Reuse existing Capture canonical schemas rather than creating duplicate databases or a parallel recorder.

## Test and implementation gates

1. Audit current main and outstanding Live Client branches; reconcile existing functionality before new code.
2. Verify addon installer **backup-and-replace** works with existing files; no manual deletion required.
3. Reconfirm authenticated read-only round trip and test configurable telemetry cadence.
4. Test Toolkit-to-Ashita command receipt/acknowledgment; do not equate receipt with successful movement.
5. In a private DSP environment, test native autofollow controls and record both client and server positions. Distinguish follow from teleport.
6. Only after the above, prototype event streaming and entity discovery with a common schema and Capture integration.
7. Before copying source, audit license, attribution, dependency provenance, compatibility and repository maintenance. Prefer adapting patterns when dependencies are proprietary.
8. Add tests, documentation, help-page links, and roadmap status when each slice is implemented.

## Open questions

- Does the installed Ashita v4 build expose the necessary autofollow interface and does it work with arbitrary coordinate deltas?
- Can native movement be controlled through existing Toolkit/Ashita integration without an additional injection hook?
- Which Cure Please events are packet-driven versus polled through EliteAPI?
- What entity/zone packet semantics can be validated with our own captures and server data?
- What are the actual licenses of EliteAPI and each candidate addon?
- How do we avoid conflict with existing Live Client, Capture, Entity, and Feature Trace features?

**Do not mark these use cases implemented based solely on this document.** This is a durable research and follow-up reference.
