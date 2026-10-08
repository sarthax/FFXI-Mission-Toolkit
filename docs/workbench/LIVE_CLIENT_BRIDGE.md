# Live Client Development Bridge — Roadmap and Resume Guide

Status: **foundation in progress** on [PR #663](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/663), branch `feature/live-client-foundation`.
First recorded: 2026-10-07. Do not describe future items below as shipped.

## Goal
Provide native Toolkit-controlled development interaction with an authorized running FFXI client, independent of the Project Tako executable. Integrate live in-game positions and entities with Zone Editor, 2D/3D spatial viewers, capture provenance, spawn placement and navmesh investigation. Development should be achievable using GitHub cloud editing/CI; runtime client validation requires a Windows FFXI session.

## Sources and decisions
- User-provided Project Tako installations: `Project-Tako.7z` (original) and `Project-Tako.zip` (updated with maps/config/plugins). These are conversation attachments, not checked into the repository.
- Reference repos: https://github.com/ProjectTako/Clipper and https://github.com/ProjectTako/ProjectTako.
- Do **not** embed Project Tako executable as the product architecture, merely forward commands to it, or copy licensed code without review.
- Favor a toolkit-managed Windows-side adapter plus transport-neutral Python orchestration.
- Do not assume offsets, signatures, navmesh availability, or instance map identity without evidence.
- Process-memory writes are disabled until authorized development session, verified client version, and adapter support. Public-server evasion is out of scope.
- Keep work isolated from ongoing GUI refactor and Auction House development.

## Implemented foundation (PR #663)
- `src/workbench/runtime/live_client/models.py`: Position, ClientSnapshot, Waypoint, PathSample and enumerated actions.
- `src/workbench/runtime/live_client/service.py`: adapter protocol, opt-in session, path observation, offline replay.
- `src/workbench/runtime/live_client/waypoints.py`: JSON waypoint/path serialization and parsing.
- `src/workbench/runtime/live_client/spatial.py`: same-zone nearby destinations, per-client/per-zone path splitting, preview-only NPC/mob placement candidates.
- `tests/test_live_client_contracts.py`, `tests/test_live_client_service.py`, `tests/test_live_client_spatial.py`: offline regression coverage.
These modules are not wired to the GUI and do not attach to or control FFXI yet.

## Development roadmap (ordered)
1. **Adapter/read telemetry:** enumerate running FFXI sessions; version-compatible zone/instance hint, XYZ, heading, character, target and entity observations; explicit disconnected/unverified states; no write operations.
2. **Spatial UI integration:** view selected client location in 2D/3D Zone Viewer, position/heading readout, camera following, version and health indication. Reuse shared shell and Zone Editor positioning conventions.
3. **Waypoints:** searchable named destinations by zone and instance hint; import validated Tako records; capture current location; categories/favorites; export/import and profile selection.
4. **Live spatial controls:** configurable small/medium/large XYZ nudge, precise position entry, up/down elevation, warp to named waypoint, warp to entity (NPC, mob, player), speed settings; carefully verify coordinate axes, clamping, updates, readbacks and server synchronization. All writable actions restricted to explicitly authorized test sessions.
5. **Development callbacks:** capture current position/heading into preview-only NPC or mob spawn proposal and submit via existing Zone Editor backup/audit/write path rather than direct DB mutation; reflect editor-selected entity back to client for locating/testing.
6. **Path capture:** timed spatial samples with zone/client boundaries, deduplication and provenance; compare to 3D spatial geometry, roaming paths, capture packet observations and zone editor.
7. **Navmesh validation:** route samples against available navmesh source; nearest valid polygon, unreachable segments, slope/height/collision discrepancies and map overlay, with explicit unsupported/unknown outcomes.
8. **Exploration tools:** collision-free traversals, climbing, client-local visibility filtering (NPC/player hiding), pause/stop/recover controls; research capabilities separately and do not silently claim support.
9. **Map resolver:** use Tako map GIS bounds as reference but validate instance- and level-specific selection; explicit override and diagnostic candidate explanations.
10. **Hardening:** multiple clients, version profiles, recorded audit trail, teardown/restoration, authorization UX, CI and optional Windows runtime smoke tests.

## Integration boundaries
- Zone/Spatial existing backend: `src/workbench/devtools/spatial/zone_plot.py` (contains navmesh reference and server selection).
- Zone Editor: `src/workbench/editors/zone/`.
- 3D viewer: `gui/templates/zone_view3d.html`.
- Capture/Research systems: preserve session/source identity and timestamps.
- Reuse existing Zone Editor write mechanisms; read-only observations and proposals must never implicitly mutate SQL.

## Resume checklist
1. Inspect newest `main`, open PRs, CI status, and the actual head of PR #663; rebase/reconcile before editing any shared surface.
2. Run or inspect regression for all three live-client test modules. Do not claim tests have passed for latest commit until workflow completes.
3. Review adapter contracts and find existing game-facing addon or telemetry interfaces before inventing signatures.
4. Implement the next *isolated* slice: client discovery/read-only telemetry interface + fixtures and tests. Follow with limited Zone Viewer attachment through existing service patterns.
5. Keep documentation status truthful, commit on `feature/live-client-foundation` or successor branch, and update this file plus roadmap at each milestone.
6. Where only GitHub cloud is available, use GitHub PR and Actions; defer actual in-game compatibility claims to an authorized Windows client test.

## 2026-10-07 additional slice: entity observation model
- Added `src/workbench/runtime/live_client/entities.py` and `tests/test_live_client_entities.py` on PR #663.
- `EntityObservation` keeps client index separate from optional observed server entity ID; categorizes player/NPC/mob/unknown and stores client, zone, instance hint and observation time.
- `overlay_observations` filters by selected client/zone and fails closed when an explicit instance is selected but the observation has no matching hint.
- `match_server_id` matches only known server IDs, never assumes memory slot equals SQL identifier.
- **Not implemented:** Windows memory reader, live entity scan, realtime GUI marker overlay, or writes. Current work is transport-neutral backend contracts and offline tests.
- Next: read-only adapter with real client telemetry, additional fixture replay and rendering adapter, then opt-in viewer integration.

## 2026-10-07 telemetry frame decoder slice
- Added `src/workbench/runtime/live_client/telemetry.py` plus `tests/test_live_client_telemetry.py`.
- Versioned read-only schema validates client, zone, XYZ, heading, time and bounded entity observations before use by GUI/service adapters.
- Server entity IDs remain optional; no inference from client index. Malformed/non-finite values fail closed.
- **No native memory attachment or actual FFXI read yet**; the decoder accepts external observations only.
- Next: a read-only Windows client adapter (or supported Ashita feed), end-to-end offline feed fixture, then live viewer overlay.


## 2026-10-07 read-only feed adapter slice
- Added `src/workbench/runtime/live_client/feed.py` and `tests/test_live_client_feed.py`.
- `TelemetryFeedAdapter` binds decoded telemetry to one explicit client identity and rejects stale or duplicate timestamps, cross-client frames, and malformed data before replacing its latest snapshot.
- Exposes a read-only `snapshot()` for `LiveClientSession.observe()` and entity observations for later overlays; no implicit discovery, memory attachment, or live game writes.
- Client-provided version text is **not** treated as a verified runtime version. Write capability is permanently false.
- Offline tests cover initial disconnect, successful observation, immutable last-good snapshot on decode failure, stale/cross-client rejection, and read-only enforcement.
- Cloud CI still requires independent verification. No live FFXI integration or GUI overlay is claimed.
- Next: add a recorded multi-frame fixture and an explicit transport/health lifecycle, then integrate opt-in viewer overlay after tests run.


## 2026-10-07 recorded replay and health milestone
- `src/workbench/runtime/live_client/replay.py`: `RecordedTelemetryReplay` advances strict frames through `TelemetryFeedAdapter` with fail-closed validation and no process attachment. Invalid frames do not advance the replay cursor.
- Explicit `FeedHealth` reports disconnected/connected/stale, last frame timestamp and count; it uses a caller-supplied clock with a validated age threshold. Future-dated frames are not considered connected.
- `tests/test_live_client_replay.py`: multi-frame transitions, zone changes, exhaustion, malformed/cross-client retry behavior, and reference-time input validation.
- No automatic runtime discovery, live connection, write operations or viewer integration yet. Tests require CI verification.
- Next: feed a stable JSON-lines recorded fixture through this interface and wire read-only session-health/position visualization.


## 2026-10-07 JSON-lines recorded telemetry import
- `src/workbench/runtime/live_client/recording.py` loads UTF-8 JSON-lines into an offline `RecordedTelemetryReplay` using the strict v1 telemetry decoder.
- Enforces explicit client identity, monotonic frame timestamps, finite decoded numeric values, default 10,000-frame and 16 MiB bounds, with blank lines ignored and malformed rows rejected with source line numbers.
- Validates the complete capture before constructing replay; no writes, code execution, process discovery, or FFXI attachment.
- `tests/test_live_client_recording.py` covers multi-zone replay, client mismatch, duplicate/out-of-order frames, malformed input, empty recordings, and size/count guards.
- CI is required before considering this slice validated; integration with an opt-in viewer is still pending.


## 2026-10-07 read-only viewer projection milestone
- `src/workbench/runtime/live_client/viewer.py`: pure JSON-compatible player/entity projection for later 2D/3D overlays; no GUI route, process attachment, or memory writes.
- The projection filters by explicitly selected client and zone; requested instance hints must match the player, and entity observations are independently instance-filtered.
- Exposes observed client indices separately from optional server IDs, entity kinds, names, XYZ/heading, and source timestamps.
- `tests/test_live_client_viewer.py`: selected-instance, wrong-client, wrong-zone, wrong-instance, and zone-only filtering regressions.
- Next: optional reader/API entry point and viewer wiring through the shared shell, coordinating with active GUI refactor. CI and Windows runtime compatibility remain separate validation steps.
