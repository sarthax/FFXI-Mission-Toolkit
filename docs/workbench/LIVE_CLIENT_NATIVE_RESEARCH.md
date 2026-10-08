# Native Live Client sources and validation boundary

This research supports the cloud replay integration work. It is source inspection,
not a claim that a Windows reader or game-client build has been verified. No
third-party implementation, memory offsets, signatures or game binaries were copied.

## Source evidence

| Source and inspected revision | Observed technique | Reuse and validation constraints |
| --- | --- | --- |
| [Windower/Lua `fdc9cb8d`](https://github.com/Windower/Lua/tree/fdc9cb8d02191e411fd4f9dbb6870fd13bda3d6e) | `InfoBar` reads `get_info().logged_in`, zone and `get_mob_by_target('me')` coordinates/facing. `DistancePlus` observes selected targets and pets in a `prerender` callback. | Prefer an explicitly started, read-only addon source over copying game offsets. Licenses vary per addon; the inspected InfoBar source has BSD-style attribution terms. API presence in source does not verify output units, active client build, disconnect behavior or entity identity. |
| [AshitaXI/Ashita-v4beta `4171c74c`](https://github.com/AshitaXI/Ashita-v4beta/tree/4171c74c8ddb2ca2a31654f199e6c1cee40d7256) | SDK `IEntity` and Lua annotations expose local position X/Y/Z, heading, name and zone; `IMemoryManager` exposes player/entity managers. | Repository licenses distinguish GPLv3 Ashita from LGPLv3 SDK. Use published interfaces with separate source/adapter identity; verify player index selection, coordinate meaning and actual runtime version before integration. Do not treat API names as proven memory layouts. |
| [ProjectTako/Clipper `228d962a`](https://github.com/ProjectTako/Clipper/tree/228d962a2f258f96e33358d3f35f9092c00844e9) | Character selection enumerates `pol` processes and checks for `FFXiMain.dll`; separate configuration-driven signatures and memory wrappers implement reads and writes. | GPLv3 source. Do not transplant code into the toolkit's MIT implementation without resolving distribution/license requirements. Process/module names alone do not verify identity or compatibility. Auto-attachment and game writes are outside the read-only adapter contract. |
| [ProjectTako/ProjectTako `98962930`](https://github.com/ProjectTako/ProjectTako/tree/989629309b50197e94932e43becbd8dd0d2ac0a3) | Public tree contains only `.gitattributes` and `.gitignore`. | No implementation or license evidence is available at that revision. Conversation-mentioned archives were not available in this cloud checkout and were not used. |

## Adapter integration contract

Use `ObservationSource` / `TelemetryProducer` and the strict telemetry v1 decoder.
Keep each connected process or addon instance separate from recording session IDs.
The adapter should report its actual source/version and observation timestamp,
player position/heading/zone, and only entity data its interface actually supplies.
Client entity indexes remain client indexes; do not silently identify them as
server entity IDs. Unknown instance identity stays unknown.

Before a native adapter is advertised as supported, validate an authorized
Windows runtime with a recorded evidence manifest: running process identity and
lifetime, loaded game-module identity, actual framework/game version, observed
field semantics, coordinate axes/heading units, zone and instance transitions,
multi-client isolation, stale/disconnected behavior, and unsupported-build failure.
The executable hash boundary in `windows_identity.py` is insufficient on its own.
No build allowlist entries can be invented from these reference sources.

Fail closed on incompatible identity or malformed observations. A disconnected
reader must stop emitting frames and distinguish its last observation from a
current connection. A replacement process must require fresh identity verification.
Preserve the explicit local file feed as an observation transport; it is not a
native process detector and does not prove that its contents came from a game.

## Development controls and spatial integration

Recorded XYZ and trace previews are cloud validated with synthetic observations.
They are not calibrated zone-map coordinates. Map overlays and Zone Editor
placement callbacks require source-proven transforms and explicit zone/instance
matching before their coordinates can be used.

Named waypoint/path serialization and preview-only placement foundations already
exist. Actual warp, speed and position writes remain unavailable without a
verified write adapter and an explicitly authorized local development session.
The existing `validate_action` checks must remain separate from observation APIs.
Any future write requires deliberate authorization, target compatibility,
preview/audit records and disconnect handling. Collision/navmesh results and
packet correlations must reference real data rather than inferred compatibility.
