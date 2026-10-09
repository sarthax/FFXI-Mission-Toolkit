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

## Toolkit capability matrix at audit baseline (#718)

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

## Ashita minimap and packet reuse follow-up

The supplied [Ashita Minimap documentation](https://github.com/StiegFFXI/Ashita-v4beta-4.16-full/blob/4171c74c8ddb2ca2a31654f199e6c1cee40d7256/docs/Minimap/README.md)
was inspected. It documents `drawmonsters`, `drawnpcs`, `drawplayers` and a target
marker texture; distribution includes `plugins/minimap.dll`. This is a strong
behavioral reference for available entity rendering, not a documented telemetry
export interface or source-level verification of map transforms. Reuse Ashita
published entity APIs and the Toolkit's own narrow observation bridge; do not
recreate the in-game minimap or require it to render/export Toolkit observations.
`IEntity:GetEntityMapSize` is published, but slot bounds/validity and enumeration
semantics still need verification before advertising full loaded-entity support.

The bridge now optionally exports `IEntity:GetServerId` for the selected target,
separately from the client index. Missing getter or zero leaves identity unknown;
invalid values fail closed. Rechecks reject target index/disappearance/name and
known server-ID changes during position reads. Original recordings still import;
kind remains unknown and version remains unverified. Synthetic Lua/file-feed tests
validate mapping/rejection; this additional getter needs Windows runtime testing.
A reported ID is an observation, not proof of the selected server/database identity.

For packet integration, reuse `workbench.packets.decode` (`list_opcodes`,
`get_field_schema`, `decode`), `captures/_raw_packet_ingest_impl.py` (PacketDB and
Packeteer ingestion), `captures/packet_correlation.py` and the existing capture
spatial services. Preserve packet direction, source bytes/locator, timestamps and
version evidence. Established framework tools can supply additional formats and
samples under their applicable licenses; no new decoder is required for covered
schemas. Decoding a capture is not proof that constructing/sending it is valid:
write support requires independently verified framing/fields/direction, selected
client/session, explicit authorization and observed client/server behavior.
No packet injection or memory write has been added.

## Bounded inventory implementation follow-up

Further pinned source inspection found `addons/petinfo/petinfo.lua`'s
`GetEntityByServerId` and `addons/chamcham/chamcham.lua` enumerate `GetEntity(0..2303)`;
`actionparse` and `truesight` use a slightly smaller upper bound. Only observation
concepts and published calls are reused; no third-party implementation, writes,
patterns or offsets were copied. This supplies a source-backed experimental range,
not proof of compatibility with the operator's loaded runtime.

The Toolkit now offers opt-in bounded named-slot inventory (32 observations,
selected-target first), preserves optional reported server IDs, rechecks observed
identities and player/zone context, and reports `observation_scope` plus truncation
through decoding, projection and UI. Blank-name and absent slots are omitted;
unknown kind/instance stay unknown. Old recording fields default to unspecified
scope. No complete-world or atomic-memory-snapshot claim is made. Cloud tests
cover upper-bound slots, caps, duplicates, missing slots, entity disappearance,
legacy mode/reset, invalid scope and Chromium truncation visibility. Windows
inventory/lifecycle tests remain pending. Backlog slice 1 has its experimental
cloud implementation; runtime acceptance and richer kind/status/target-role
semantics remain open. Next gather runtime evidence, then identity/calibration.

## Portable path provenance follow-up

The earlier baseline `PathSample` metadata gap is now closed: optional instance,
source/version, session/generation, segment and scope/truncation survive portable
round trips. Session sampling retains known snapshot metadata; export supplies
recording context. Source/version changes split replay trace segments as well as
paths. Unknown legacy context stays unknown and non-increasing times break paths.
This is cloud-validated evidence preservation; calibrated maps, navmesh traversal,
actual runtime identity and client controls remain separate pending work.

## Reconciliation with Ashita capability research — 2026-10-09

Authoritative baseline: `main` at `0d6f46ba`, including [PR #753 research](ASHITA_V4_CAPABILITY_AUDIT_2026-10-08.md), entity inventory (#725), replay entity markers (#744) and waypoint generation isolation (#742). This matrix supersedes stale *current* claims in the #718 baseline above; historical evidence remains retained. No open Live Client PR was found. Remote recording-management (`1d32ec9c`) and spatial-trace (`84c3a5e0`) branch heads are already ancestors of main; no unfinished work was discarded. Wiki/Auction House branches remain outside this change.

Classifications apply to individual functions, not entire providers: **runtime verified** below means only the limited supplied observation evidence; it never means a supported build. **Offline** means implemented with synthetic/cloud tests. **Partial**, **upstream only**, **native required**, and **blocked/unsupported** retain their ordinary literal meanings.

| Capability / classification | Existing Toolkit | Existing Ashita addon | Published Ashita evidence | Existing native Windows work | Missing / duplication to avoid | Windows verification required |
| --- | --- | --- | --- | --- | --- | --- |
| Player XYZ/heading/zone — implemented, runtime verified within supplied sample | Strict telemetry, file feed, replay/path/waypoint models | One-second explicit sampling, party zone and identity rechecks | IEntity local position/heading; IParty zone | Disk identity helper only | Keep existing exporter/decoder; transforms remain missing | 121 frames/120 seconds, zone 50, stairs; zoning, heading units and loaded build still pending |
| Observation providers — implemented, offline | ObservationSource.observe, TelemetryProducer, feed and optional frame-provider router; source/version in snapshots | Original Ashita and Windower entry points share helpers | Published manager interfaces | No process source | Existing abstractions accept future sources; do not add competing schema/registry | Per-provider compatibility and lifecycle |
| Independent recording/session identity — implemented, offline | Registry generations, duplicate client IDs, replace/unload, stale-token rejection | Explicit unique exporter IDs and fresh bounded files | One addon per injected client | No OS discovery | Retain registry; actual two-client evidence missing | Two clients, restart, zoning/logout/unload |
| Entity enumeration/index/name/XYZ — runtime observed in supplied bounded samples; heading remains separately unverified | Decoded entity model, table, raw-plane markers, scope/truncation | Opt-in slots 0..2303, cap 32, target first, nil/blank/player exclusions and identity rechecks | Pinned petinfo/chamcham examples and IEntity | No native enumeration | Do not reimplement scan; not a complete census or despawn detector | Supplied 30-frame zone 235 and 24-frame zone 107 inventory samples accepted; slot reuse, performance and cap/truncation still pending |
| Reported server ID — runtime observed as nonzero values; server identity unverified | Separate optional ID; no automatic server identity promotion | Optional GetServerId, zero/missing unknown | IEntity uint32 server ID | None | Independent selected-server ID validation missing; never equate index and SQL ID | 1,035 nonzero ID observations accepted; compare known NPC/mob/player IDs and slot reuse |
| Raw entity type/status/spawn flags — upstream only at reconciliation baseline | No preserved raw fields yet; kind remains unknown | Not sampled yet | IEntity GetType uint8; GetStatus/GetSpawnFlags uint32 | None | Highest-value additive entity slice; no enum/semantic guesses | Getter availability, bounds, meanings and transitions |
| Target/subtarget designation — partial | Entities exist, roles not retained | Index 0 observed, not distinguished when subtarget active | targets.lua: active subtarget is slot 0, original target slot 1; GetIsSubTargetActive | None | Add explicit roles only when role API available; retain unknown legacy roles | Normal target, subtarget, same-slot roles, changing target |
| Validity/staleness — partial | Finite/schema/time/client checks; last-good feed preserved | Player/zone/entity/name/known-ID rechecks; rejected samples stop | API availability and entity existence checks | No process lifetime validation | Keep rejection guards; raw status is not verified liveness; absence is not despawn | Logout/unload/disappearance/replacement and restart |
| Replay/UI/waypoint/path tooling — implemented, offline | Playback/speed/seek/compare; persistence, generation guards, full path export and raw trace planes | Supplies existing v1 frames | No replacement UI needed | Provider-neutral | Retain all work; no second console or minimap implementation | Existing log exercises replay; actual same-host live polling pending |
| Loaded framework/client compatibility — partial | Bounded runtime report, supplied-file PE metadata and caller-provided executable digest manifest | Reports explicitly unverified API version | SDK interface/version evidence only | Disk hashing only; no process/module attachment | Add actual loaded-module/PID lifetime evidence later; no invented allowlist | Loaded build, bitness, hashes, unsupported/disconnect behavior |
| Standalone observation without launcher — native adapter required | Producer/feed seams ready | Requires Ashita | Does not imply external OS reader | No reader implemented | Independent explicit process selection and verified attachment | Authorized Windows process/module/lifetime validation |
| Passive packet observations — upstream only | Canonical raw ingestion, packet schemas/decoder/correlation already exist | No packet stream/hook registered | packet_in/packet_out; exact original/modified Lua semantics still to pin | None | Add optional source adapter into Capture; no parallel decoder | Direction/byte/length/stage, injection/block labels, caps/filtering, comparison capture |
| Entity spawn/despawn timeline — blocked for definitive events | Observed snapshots only | Bounded subsets can omit entities | Entity/packet hooks are research leads | None | Distinguish observed disappearance from proven despawn | Independent event evidence under churn/truncation |
| Appearance/equipment/animation — upstream only | DAT/Model and Item/Equipment services available | Not exported | GetAnimation/GetLook*/inventory/resource getters | None | Add opt-in compact observations, reuse existing viewers; no assets/pointers exported | Values and timing against known actions and resources |
| Party/player/recasts/abilities — upstream only | No Live Client diagnostic bridge | Player party identity used only | IParty/IPlayer/IRecast | None | Independently test opted-in diagnostic profiles | State availability/staleness, version and semantics |
| Mission/key-item direct state — blocked/unsupported as a promised API | Capture/event/CSID and script evidence available | Not exported | Audit has no proven stable direct mission-flag API | None | Research per-method evidence; do not invent decoder semantics | Known event capture and independent server evidence |
| Entity Browser/Feature Trace/Behavior/Capture joins — partial | Existing graph, dossier, packet/spatial and behavior services; no live-source join | Source identity and raw observations only | Candidate entity/packet evidence | None | Add read-only evidence adapter with source/time/zone/instance/ID uncertainty; no name-only joins | Independently confirmed server IDs and clock/event alignment |
| Calibrated 2D/3D/Zone Editor/navmesh — partial | Raw traces/projection, placement-candidate contracts, existing Zone Editor writer and mesh tools | Raw coordinates only | Raw getters do not establish transform | None | Verified transforms, explicit selected-server/instance previews; reuse existing editor audit path | Multiple landmarks/elevation/headings and actual selected mesh |
| Warp/nudge/speed/elevation/collision controls — native required; operationally unsupported | Action enum and fail-closed authorization/version/write-support gate only | No game writes | No supported control API proven in audit | No writable adapter/profile/audit/restore implementation | Preserve separate control boundary; no Clipper/Tako code or offsets adopted | Action-specific authorized compatibility/readback/restoration tests |

### Opt-in transition recovery test slice

Ashita 0.4.0 adds `inventory-zoning`: a private tagged player-entity/name mismatch
can pause telemetry for up to 30 seconds, sampled at most once/second. Original
identity and same-zone agreement over two successful samples gate resume. Other
errors, observed inactive party, identity changes, clock/storage failure and timeout
remain fatal. Existing immediate-stop modes are retained. No rejected/interpolated
frames, new schemas, offsets, providers or game writes; packet observation stops
when telemetry context is paused. Synthetic regression verifies behavior; actual
zoning, inactive party during loading, logout/relogin and loaded compatibility remain
unverified. This is not a claim that every transition can recover or that unobserved
logout boundaries can be detected. The supplied single-zone runtime files and identity
mismatch screenshot motivated this bounded, explicitly enabled Windows test package.

### Provider decision and next sequence

Keep telemetry v1, decoder, registry, feeds, session generations and recorded UI authoritative. The existing ObservationSource/TelemetryProducer and decoded-frame router are already provider-neutral. Ashita is the preferred observation provider; Windower remains an offline-tested alternative and a future native provider may emit the same contract. LiveClientAdapter/validate_action remain the separate control gate foundation, not evidence of an implemented control adapter. No central routes, navigation, Capture database or unrelated schemas need changing for entity expansion.

1. Add optional raw entity type/status/spawn flags and source-reported target roles to the existing addon, entity model, decoder and projection. Missing APIs/legacy recordings remain unknown; sample rejection and output bounds stay intact.
2. Pin passive Lua packet hook semantics, then implement a bounded explicitly enabled stream and canonical Capture ingestion adapter; preserve original/modified distinction and unknown opcodes. Reuse workbench.packets.decode and capture_raw_packets.
3. Add source/time/ID-qualified research evidence adapters, followed by separately enabled animation/item diagnostics. Keep existing Entity Browser, Feature Trace, Behavior Inspector and editors authoritative.
4. Obtain Windows inventory/role/lifecycle/multi-client evidence, then calibration and selected-server map/placement/navmesh integration. Useful cloud work is not blocked while those tests wait.
5. Develop native process identity/standalone reads and individual authorized controls only where Ashita lacks a supported interface. No copied offsets, auto-attachment, writable profile or restoration guarantee is justified now.

No completed functionality is superseded. Ashita supersedes the *need to implement a second memory reader for API-accessible observations*, not the independent native fallback or future verified control work. Minimap behavior is reference evidence, not a new export/provider or competing Toolkit UI.

### Supplied bounded inventory runtime evidence

Two operator-supplied Ashita telemetry recordings validate completely:

| Source | Frames / duration | Zone | Entities per frame | Total observations | Distinct slot/ID identities | Inventory-set changes |
| --- | --- | --- | --- | --- | --- | --- |
| telemetry-test-a-1791514258-1.jsonl | 30 / 29 seconds | 235 | 19–21 | 613 | 21 | 2 |
| telemetry-test-b-1791514491-1.jsonl | 24 / 23 seconds | 107 | 11–20 | 422 | 20 | 6 |

Original SHA-256: A `1555cec54d9f99c3c945e36033b5f9066240fb8f363cc399a4d7e930f1722395`;
B `f5b7e5688154b86ddb28b43f8aa6c00d2353b565cd0e8619b86c30d173093a4e`.
Both declare bounded_loaded_entities, one-second cadence, no truncation and nonzero
server IDs for every entity observation. Raw player XYZ/heading changes are present.
These files extend actual runtime observation evidence to populated zones and entity
inventory; matching server catalog identities and complete enumeration are unverified.
Changing inventory sets do not prove spawn/despawn: loading, range and other causes
remain possible. Neither file contains zoning, overlapping live sessions, slot reuse,
instance hints, raw entity type/status/spawn flags, explicit target roles or packet data.
The records still declare unverified-ashita-v4-api; loaded build/compatibility, logout,
disconnect/restart, target/subtarget semantics, cap behavior and packet fidelity remain
pending. Separate recordings in different zones do not establish an observed transition.

Operator-reported sequence: one client, test A login/walking in Bastok Markets,
zoning toward North Gustaberg, target selection/combat and logout; test B relogin,
walking in North Gustaberg, then Bastok Mines/Zeruhn Mines and combat. The file
coverage above does not capture those zone transitions, combat actions or lifecycle
boundaries. Current exporter behavior closes the file on any sampling validation
failure (including inactive party, unavailable entities or mixed zone/identity),
prints Export stopped, and requires explicit restart. The supplied test-B screenshot confirms export started, then stopped at
workbench_observation.lua:85 with player identity mismatch before the Bastok Mines
and Zeruhn Mines messages. Repeated addon-load attempts reported already loaded;
these were not an initial load failure. The guard requires an available player entity
and agreement between its name and the party name. The screenshot identifies the
failed guard, not whether transient zoning data or another discrepancy caused it. Selecting targets is not evidence of target-role
export because neither file contains target_roles. No concurrent-client test occurred.

Capture C (`telemetry-test-c-1791515026-1.jsonl`, original SHA-256
`2abde0db01722ed3dcf40b683c88ba45c1882d8e53dab20a44954fbe6de5e888`)
adds 99 frames/98 seconds in Zeruhn Mines (172): 32 entities and declared truncation
in every frame, 3,168 nonzero reported IDs and 40 distinct slot/ID identities. This
establishes supplied output at the cap, not full census or verified ID semantics.
Reported warp/zoning actions have no recorded destination-zone frames; continuity
remains pending. An anonymized capped runtime fixture now supplements A/B coverage.

Regression fixtures anonymize client/character/entity names and shift timestamps while
preserving cadence, coordinates, indexes, reported IDs, duplicate-name relationships and
inventory changes. Fixture hashes therefore differ from the original source hashes above.
Cloud tests exercise strict decoding, projection, report boundaries and independent replay;
independent replay is not proof of simultaneous connected game clients. No native controls,
coordinate transforms, graph relations or packet interpretations are promoted by this evidence.

### Entity slice implementation follow-up

The baseline raw type/status/spawn-flags and target-role gaps above now have an
additive implementation, classified **implemented but only synthetically/offline
tested**. IEntity raw getter widths come from pinned `4171c74c` SDK/annotations;
target roles follow its published targets.lua get_t/get_st behavior. Missing APIs
stay unknown. Invalid available-getter output and identity/target/context changes
reject the frame, without claiming an atomic memory snapshot or verified liveness.
The existing decoder/feed/replay/model/projection/entity table retains the fields;
legacy recordings and Windower remain compatible. Existing explicit start, one-
second cadence, 32-entity cap, 64 KiB line and 16 MiB file limits are retained.
Windows acceptance remains required for each new field and role. No packet hook,
new native reader, server join, calibrated placement or game write is implemented.

### Passive Ashita packet source / canonical Capture — 2026-10-09

The original workbench_live addon now offers a separately enabled `event_emote`
packet profile tied to active telemetry recording identity. It observes incoming
0x034/0x05A and outgoing 0x05D only, stores e.data original hook-buffer bytes and
hook-time flags, and never modifies packet events or captures raw pointers/chunks.
Bounds are 10 accepted packets/second, 1024 packet bytes, 4096 line bytes, 4 MiB
and 10,000 records; excess-rate drops are counted. Identity/context/clock/format/
IO failures stop safely. Telemetry stop/failure and unload close the packet stream.

Existing Capture Add Files, folder/archive ingestion and source rebuild recognize
this source through a narrow adapter into capture_raw_packets and existing source
locators. Direction, UTC-second time, sequence, zone, source identity, raw hex,
reported opcode/length, drops and hook-time injected/blocked flags remain evidence.
Original/header disagreements retain both values; unknown semantics stay unknown.
No second packet decoder, Capture schema, UI or game-write mechanism was added.

Published hook-field evidence is AshitaXI/example at
[92434ef5](https://github.com/AshitaXI/example/blob/92434ef51d464fbc5d5a8513e30ecbad60321fd6/example.lua),
packet_in/packet_out documented argument blocks: e.data is read-only, while
modified/raw/chunk surfaces are separate. These are reference API names/behavior;
Toolkit implementation is original MIT code, with no copied upstream mutation.
This slice is **implemented but only synthetically/offline tested**. Hook-time
flags are not final blocking and hook bytes are not independently verified wire
traffic. Actual Windows hooks, performance, packet fidelity and clock/event joins
remain pending. The profile is deliberately narrow, not a complete event census.

Next: runtime packet/telemetry correlation evidence and source/time/zone/ID-qualified
research links through existing Capture/Feature Trace services. Further diagnostic
profiles, calibration and native controls remain independent future work. See the
[addon instructions](../../addons/workbench_live/README.md#optional-passive-packet-observations-ashita-only).

### Paired offline temporal evidence (cloud-tested)

The runtime-report CLI now optionally reads a stopped packet JSONL using the canonical
Capture adapter's strict validator. It emits bounded exact label/source/zone/time
candidates with packet line/byte and telemetry-frame locators, plus both source hashes.
This supplements the existing Capture importer and recording reports; it replaces no
provider, schema, decoder, replay, UI or identity service. It does not join entities by
client index or server ID, infer packet semantics, interpolate across missing frames,
create Feature Trace relationships or promote declared labels into verified identities.
Same-time ambiguity remains unmatched, and instance/clock/wire/causal verification is
explicitly absent. Paired Windows exports and reviewed Capture/Feature Trace UI links
remain future work. The supplied player-only runtime recording still establishes only
its previously documented observation coverage.

### Existing research view handoffs (cloud-tested)

Live Client entity rows now offer Capture entity evidence, Entity Browser and Feature
Trace ID searches when a nonzero server ID was explicitly observed. Queries use that
reported ID only, never client slots, names, guessed raw entity types or invented graph
nodes. Existing destination resolvers and decoders remain authoritative. Links open in
another tab so playback remains available; tooltips retain source client/adapter,
observed zone/instance/time, and identify the search as unverified. Results can come
from other indexed contexts and require identity, zone and instance review. Unknown
IDs expose no links, and entity filtering/frame refresh removes obsolete rows.
This is a research navigation handoff, not a verified entity join, packet/frame binding
or new Feature Trace relation. Synthetic projection/browser tests cover these paths;
Windows ID observations and catalog/runtime identity agreement remain pending.
