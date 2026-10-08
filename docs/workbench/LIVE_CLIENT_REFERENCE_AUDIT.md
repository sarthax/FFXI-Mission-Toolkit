# Tako / Clipper reference audit and native bridge decision

Audit date: 2026-10-08. Toolkit baseline: `38514fe53e9d86f8050d66e466db450164b8125a`
(PR #718). This is static source inspection plus previously supplied runtime
artifacts, not a Windows attachment/control test. Current capability inventory
supersedes the dated foundation entries in the resume guide.

## Inspected evidence and availability

- Cloned [Clipper at `228d962a`](https://github.com/ProjectTako/Clipper/tree/228d962a2f258f96e33358d3f35f9092c00844e9):
  README, LICENSE, project/configuration, character selection, globals, memory,
  signature scanner, pointer factory, player partial classes and main/settings UI.
- Cloned [ProjectTako at `98962930`](https://github.com/ProjectTako/ProjectTako/tree/989629309b50197e94932e43becbd8dd0d2ac0a3):
  tracked tree contains only `.gitattributes` and `.gitignore`. No implementation,
  assemblies, map definitions or license were available there.
- Cloned [Ashita v4beta at `4171c74c`](https://github.com/AshitaXI/Ashita-v4beta/tree/4171c74c8ddb2ca2a31654f199e6c1cee40d7256):
  license policy, SDK entity header and Lua `IEntity`, `IParty`, `ITarget` annotations.
  Windower observations remain based on the earlier pinned source research in
  [native source research](LIVE_CLIENT_NATIVE_RESEARCH.md); its repository was
  not independently re-cloned for this audit.
- Read the Live Client bridge, Windows handoff, authoritative current roadmap and
  historical `docs/guides/ROADMAP.md`; inspected Live Client contracts, identity,
  exporter, telemetry, service, replay/export, waypoint/comparison code and tests,
  host routing, Zone Editor position writer and spatial/navmesh integration seams.
  #663 is merged; subsequent #687, #691, #693, #698, #701, #702, #706, #713 and #718
  extend that foundation. Open #703/#707/#717 concern Wiki and are outside scope.
- Workspace attachments contain the supplied Ashita JSONL, EXE/DLL and pasted
  text. **Project-Tako.7z, Project-Tako.zip and all three Tako screenshots were
  unavailable.** No archive or screenshot inspection is claimed. Supplied Ashita
  files were previously parsed, not executed; metadata and hashes are retained
  in `tests/fixtures/live_client/ashita_supplied_binary_metadata.json`.

Evidence labels below: **source-confirmed** means implementation was read, not
that its current game behavior works; **runtime-partial** means supplied recording
plus operator report; **historical lead** means prior research/user description
without accessible implementation. No historical count is promoted to fact.

## Reference inventory

All Clipper paths in this table are relative to its pinned repository. **Reference
only** means no implementation/signature/offset has been copied into the toolkit.

| Area | Source / symbol | Observed implementation and limits | Confidence / reuse |
| --- | --- | --- | --- |
| Discovery | `Clipper/frmSelectCharacter.cs`, `LoadCharacterList`, `ProcessEntry` | Enumerates `pol`, checks loaded `FFXiMain.dll`, displays window title; automatically selects the sole candidate. Global `CurrentProcess` supports one active process, not simultaneous readers. No loaded-module hash/build validation. | Source-confirmed; adapt discovery concept, require explicit selection and PID lifetime verification. |
| Windows access | `Classes/Memory.cs`, `Memory.Peek/Poke`, `NativeMethods` | P/Invoke `ReadProcessMemory`/`WriteProcessMemory` using `Process.Handle`; wrapper returns API boolean without validating transferred byte count. No explicit least-privilege `OpenProcess` boundary here. | Source-confirmed; reference only. New reader must check full reads and access rights. |
| Resolution | `Classes/SigScan.cs`, `DumpMemory/FindPattern`; `PointerFactory.UpdateFactory` | Dumps module, checks dump byte count, masked first-match scan plus configured offset; missing signatures produce critical error/false. First match is not a uniqueness check. Caches dump, resets pointer table on update. No compatibility allowlist. | Source-confirmed; adaptable requirements, no signatures reused. |
| Profiles | `Classes/Configuration.cs`, `Signature`, `Offset`, `Patch`; `Program.cs`, settings save | XML configuration provides pattern/mask/offset and enabled/disabled patch bytes; settings serialize configuration. Existence of fields does not prove a profile for current FFXI. Project targets .NET Framework 4.0, with AnyCPU and x86 configurations; pointer arithmetic assumes 32-bit values. | Source-confirmed; versioned profile concept only. |
| Player / zone | `Classes/Player/Player.cs`, `GetPointer/GetZoneId/Name` | Resolves own entity through configured own-position and entity-table pointers; separate zone pointer chain. Many reads are unchecked or return fallback values. No heading/rotation observation API found in this class. | Source-confirmed; reference only, not current structure verification. |
| Entities | `Player_AutoDetect.cs`, `ScanForPlayers` | Iterates 4,000 pointer slots, reads name/type/spawn flags/render/distance, with name and visibility filters. This is a player-detection feature, not a complete entity browser or proven target/server-ID resolver. Memory slot is not SQL identity. | Source-confirmed; bounded enumeration idea only. Detection/evasion behavior is excluded. |
| Position | `Player.cs`, `AdjustPosition`, `PositionDirection` | Reads warp-position structure and updates two coordinate locations per affected axis. Supports eight horizontal directions plus up/down. Source uses Y for north/south, X for east/west and negative Z for up; diagonal amount is a custom calculation, not normalized distance. Partial writes are not rolled back. | Source-confirmed; behavioral reference only. These conventions must not be applied to Ashita or server coordinates without calibration. |
| Speed / status / flags | `Player.cs` properties; `Player_Speed/Status/Flag.cs`, `Enable*Hack` | Repeated writes in worker loops; speed attempts to remember a previous value, status/flag reset to constants. This is not a general restoration journal or transactional control interface. README associates status/flag with clipping; no collision solver is present. | Source-confirmed implementation; collision effect is README claim, not tested here. Reference only. |
| Elevation / action delay | `Player_ZCoord.cs`, `EnableZCoordHack`; `Player_JAWait0.cs`, `Enable/DisableJAWait0` | Repeated Z assignment; configured instruction patches enable/disable action behavior. Z exit clears setting, not a captured original position. Patch restoration depends on configured disabled bytes. | Source-confirmed; no hook or patch adopted. |
| Warp / waypoint | Clipper inspected tree; historical Tako Warper tab | No named-waypoint manager, direct XYZ warp-to-target/entity interface or persisted location schema found in Clipper. Tako Point Manager/Set Position/Entities in Memory are historical/user-observed leads. | Clipper source scope confirmed; Tako historical lead, only UX reference. |
| Maps / instances | Historical `Config/tako.mapdata.json`, `maps/{zone}_{level}.gif`, `GetMapDataForCurrentZone` | Reported 731 images, 1,424 definitions, 278 zones, 85 multi-map zones, 1,801 waypoints and 38 pointers are unverified here. Selection bounds, level/instance identity and transform formulas cannot be recovered from public tree. | Historical lead only. No resource redistribution or calibrated overlay justified. |
| Resource origin | Historical updater URL, `DownloadFile/DownloadString/GetFFXIInstallPath` | Names suggest both remote and local resource access but do not establish GIF download, DAT extraction or generation. No updater manifest fetched, no archives available. Exact map provenance remains unknown. | Historical lead; needs manifest/archive/source inspection and resource rights. |
| Plugins / hooks | Historical `ITakoPlugin`, `LoadPlugin/UnloadPlugin`, `PluginControl/PluginCommand` | Reported Core/ResourceManager/ExamplePlugin/MovementPlugin/AllMaps assemblies and NavMesh reference unavailable. No exact signatures, lifecycle or hook contract verified. Clipper inspected code uses process reads/writes, not a demonstrated plugin API. | Historical lead only; do not implement against guessed contracts. |
| Navigation / synchronization | Clipper main worker / player classes; historical missing NavMesh DLL | Zone cooldown exists; process-exit check skips scan. No server acknowledgment, collision geometry, route solver, readback transaction or robust reconnect identity contract demonstrated. Map mistakes in instances are user reports, not diagnosed implementation bugs. | Source-confirmed limitations; navmesh presence in Tako unknown. |
| Ashita observations | `IEntity:GetLocalPositionX/Y/Z/GetHeading/GetName`, `IParty:GetMemberZone`, `ITarget:GetTargetIndex` | Published APIs used by toolkit's original Lua source. SDK entity ZoneId is conditionally populated, so exporter uses local party zone and rechecks identity/zone after sample (#698). APIs also expose `GetServerId/GetSpawnFlags/GetStatus`, but toolkit does not currently export a full loaded-entity inventory. | Source-confirmed APIs plus runtime-partial existing exporter; adapt through published interfaces, verify additional semantics. |

### Licensing decision

Toolkit root license is MIT. Clipper root `LICENSE` contains **GPLv3**, while
inspected C# headers say **LGPLv3-or-later**. The earlier shorthand “GPLv3 source”
is incomplete: resolve per-file licensing/authorization before copying or linking.
MIT code can participate in a GPL distribution under applicable terms, but that
does not permit silently labeling copied GPL code as MIT. LGPL reuse would also
require its applicable notices, source/modification and linking obligations.
No Clipper code, patterns, patch bytes or offsets are included in this change.

Ashita `LICENSE.md` specifies GPLv3 for the application and LGPLv3 for the SDK.
Continue original toolkit addon code through published APIs; do not bundle or
modify framework/SDK code without assessing the relevant distribution obligations.
Tako binaries/resources have no independently inspected licensing evidence here.
Archive access would enable analysis, not automatically authorize redistribution.

## Toolkit capability matrix

Statuses describe the bridge, not independent pre-existing Zone tools.

| Capability | Classification | Actual evidence / remaining boundary |
| --- | --- | --- |
| Ashita player XYZ/heading/zone and selected target | **Working in actual game, limited evidence** | Operator-reported success; 121 frames/120 seconds, zone 50, stairs, eight selected-target identities. Exact loaded build, units, heading conventions and lifecycle remain unverified. |
| Windower exporter | **Implemented but not runtime-tested** | Original Lua uses published API; offline Lua tests only. |
| Windows detection / native process attach | **Not implemented** | `windows_identity.verify_client_executable` hashes a selected disk file against caller-provided manifests; it neither enumerates processes nor validates loaded module lifetime. No supported runtime profile established. |
| Loaded entity table / kind / server IDs / status | **Not implemented in exporter** | Ashita exports selected target only, kind unknown, no server ID/status. Decoder/model can accept more entities; that contract is not an entity scan. |
| Current target designation | **Working in actual game, limited evidence** | Selected target observation exported; no explicit target-role field in telemetry v1. Windower may also export subtarget/pet without role tags. |
| Instance/map identity | **Blocked pending Windows evidence** | Ashita exporter emits no instance hint; null means unknown. Zone ID alone cannot identify map floor/instance. |
| File polling / connection health | **Implemented but not runtime-tested** | Explicit local JSONL FileBridge, bounded polling, last-good data and stale/error reporting. Same-host running-client polling has not been validated. Cloud cannot read Windows local files. |
| Replay, multi-recording and shared UI | **Offline/replay only** | Upload/replace/unload, identical client IDs isolated, timed playback/speed/scrub, observation compare and raw plane traces; API and Chromium regression tested. Not OS multi-client discovery. |
| Persistent named waypoints | **Offline/replay only; host persistence implemented** | SQLite library, capture/filter/rename/delete/atomic import-export; raw comparisons require session/source/zone/visit. Reloaded recording gets new session; old points remain stored but excluded from comparison. No game warp. |
| Timestamped paths | **Offline/replay plus partial game capture** | Lua exporter samples at most once per wall-clock second (not configurable), bounded JSONL. Replay path export retains XYZ/heading/time/client/instance up to cursor; source provenance is document-level. `LiveClientSession.PathSample` omits instance/source/version; not a full durable capture contract. |
| Native control / restore | **Interface/stub only** | DevelopmentAction enum and `validate_action` gates; current adapters refuse writes. No nudge/set-position/speed/visibility/collision/warp/elevation implementation or restore audit. |
| Live 2D/3D map overlays / camera following | **Not implemented** | Raw SVG trace and pure viewer projection exist; not calibrated zone viewer overlays. |
| NPC/mob placement | **Interface/stub only for Live Client** | `placement_from_sample` creates a preview dataclass, not editor callback or validated identity/transform. Existing Zone Editor writes/backups/journal are separate. |
| Navmesh traversal validation | **Not implemented for Live Client** | Zone tools already have point diagnostics/routes using available server navmeshes. No transformed live path comparison, calibrated height/collision or roaming verdict. |
| Capture / Entity Browser / Feature Trace correlation | **Not implemented for Live Client** | Existing services available; no automatic promotion from target index/name to server identity or packet correlation. |
| Zoning, logout/reconnect, unsupported clients, two live clients | **Blocked pending Windows evidence** | Synthetic tests and stop guards do not establish runtime behavior. Supplied DLL/EXE versions 4.0.0.2 are disk-file identities, not loaded-runtime proof. |

## Architecture decision and integration map

Use three layers; no Tako executable dependency and no command forwarding.

1. **Observation:** extend original Ashita addon first. Its published interfaces
   and existing runtime sample offer a narrower compatibility burden than a new
   signature scanner. Keep bounded JSONL/local feed transport and strict decoder;
   expose actual source/capabilities separately from verified support. Explicit
   exporter IDs, process/addon generation and recording session IDs remain distinct.
2. **Control:** separate optional adapter with per-action capability and explicit
   authorized development session. No writable profile is currently justified.
   Future commands need versioned request IDs, session generation, preconditions,
   audit, bounded values, readback and supported restoration; never replay writes
   or reuse a replacement process. Broad patching is not the initial control slice.
3. **Development integration:** stage observations/candidates in existing Toolkit
   tools, with selected server environment and verified transforms. UI never
   silently converts raw heading into server rotation or client index into entity ID.

| Existing seam | Reuse / prerequisite |
| --- | --- |
| `addons/workbench_live/workbench_observation.lua`, `workbench_export.lua` | Extend API-backed capture and bounded explicit lifecycle; no offsets. |
| `runtime/live_client/telemetry.py`, `producer.py`, `file_bridge.py`, `registry.py` | Versioned validation, original observation source, bounded local transport and independent sessions. Add capabilities/lifecycle evidence without duplicating replay. |
| `runtime/live_client/service.py`, `models.validate_action` | Keep write gate separate; add verified per-action adapter before control UI. Existing boolean gate alone is insufficient authorization/audit design. |
| `runtime/live_client/waypoint_library.py`, `observation_exports.py`, `replay_console.py` | Reuse storage, provenance, path exports and shared UI; add calibrated views only with verified transforms. |
| `runtime/live_client/spatial.py`, `viewer.py`, `entities.py` | Preview/projection contracts and explicit known server-ID matching; preserve unknown kind/instance. |
| `devtools/spatial/zone_plot.py`, `nav_diagnostics/nav_route`; `devtools/domains/nyzul_plot.py` | Reuse selected-server navmesh parser/point/route results; verify axes/units and selected mesh identity before comparisons. Missing mesh means unsupported. |
| `editors/zone/editor.py`, `_editor_impl.update_position`; host `/zoneplot/edit` | Existing writer backs up row, updates selected environment, journals SQL; direct endpoint is a write, not a proposal validator. Add explicit reviewed placement preview with server/zone/entity/version preconditions before invoking existing editor workflow. Do not call from observation. |
| `gui/templates/zone_view3d.html`, `src/workbench/app/_host_impl.py` | Existing shared UI and route registration; calibrated overlay/camera integration remains separate. |
| `workbench/captures/spatial.py`, `captures/packet_correlation.py`, `core/services/client_entity_graph.py`, `feature_trace_providers.py` | Preserve evidence locators/timestamps/source; correlation needs explicit verified server identity and compatible capture timebase. No name-only promotion. |

**Standalone helper versus Ashita:** an Ashita addon depends on Ashita and its
in-process lifecycle but outsources changing game layouts to published interfaces.
An original Windows helper would remove that launcher dependency and enable
process/module identity enumeration, but owns access rights, bitness, pointer
profiles, signature uniqueness, lifetime races and every game update. Recommend
an identity-only read-only helper as a later independently tested slice; do not
start memory controls by importing old Clipper profiles. Both can implement the
same narrow versioned observation/control boundary. A cloud deployment alone
cannot access local client memory; the helper/addon must run on the test host.

## Prioritized slices and acceptance criteria

| Order | Slice | Acceptance / dependency |
| --- | --- | --- |
| 1 | Bounded read-only Ashita loaded-entity inventory | Verify documented entity slot bounds and validity; cap work/frame and output; separate index/server ID/kind/status/target roles; recheck player/zone around sample, fail safely on disappearances. Lua/decoder/Chromium tests, then Windows target-switch/unload/zoning evidence. Unknowns remain unknown. No API names treated as proven semantics. |
| 2 | Runtime identity/lifecycle manifest | Operator records game/framework and loaded module identity; optional original helper enumerates candidates with explicit selection, PID/start-time/module hash/bitness. Denied access, exit/PID reuse, unsupported builds and two clients tested on Windows. Disk PE metadata alone insufficient. |
| 3 | Configurable path capture | Bounded sampling rate/frame/file limits, monotonic observation handling and retained client/source/version/heading/instance transitions. Preserve legacy JSONL imports; test clock rollback, restart and incomplete line handling. |
| 4 | Calibrated overlay and placement preview | Verified source-to-server axis/heading/units transform from multiple landmarks and elevation; select server, zone, level/instance and explicit target entity. Show unknown/map ambiguity; preview only by default, reject stale/wrong context; submit through existing editor backup/journal workflow with separate deliberate confirmation. |
| 5 | Navmesh evidence comparison | Selected actual mesh and calibrated path; classify known polygon/height/connectivity results separately from unavailable mesh/transform/instance. Test disconnected and discontinuous synthetic paths, then real traversal against that mesh. |
| 6 | Minimal verified control adapter | Start with one authorized XYZ operation, supported version profile, audit/preview, full readback, clear rejection and disconnect behavior. Windows client/server acknowledgment or observed correction recorded; no blanket speed/collision/visibility support. |
| 7 | Additional controls / temporary override restoration | Add actions individually only after adapter evidence: nudge, waypoint/entity warp, speed, elevation then any local visibility/collision behavior. Capture original state, identity-bound teardown and restoration limits; unsupported restoration blocks advertising temporary overrides. No detection-evasion feature. |

Cloud CI proves decoding, bounds, provenance isolation, mock API mapping, persistence,
preview rejection and browser behavior. Windows tests must establish actual loaded
identity, field semantics, entity churn, zoning/logout/reconnect, two-client isolation,
unsupported-build refusal and (later) every authorized write/readback/restore.
Use the [Windows handoff](LIVE_CLIENT_WINDOWS_HANDOFF.md) to collect artifacts;
local Codex is optional. Current baseline: 128 Live Client tests and six PR #718
checks passed; those results are not native compatibility evidence.

Archive-dependent follow-up: inspect supplied assembly metadata/interfaces with
hashes, updater manifest/config references, actual map records and rights. Verify
GIF provenance and selection logic before diagnosing instance-map bugs or
importing Tako waypoint/map formats. Continue public-source development meanwhile.

**Concrete recommendation:** implement and runtime-test the bounded Ashita entity
inventory first, then establish identity/lifecycle and coordinate calibration.
That advances independent position/entity observation without Tako and supplies
credible prerequisites for one deliberately authorized position-control adapter.
