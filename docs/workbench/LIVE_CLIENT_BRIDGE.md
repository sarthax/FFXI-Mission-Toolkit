# Live Client Development Bridge — Roadmap and Resume Guide

Status: **recorded sessions integrated; partial Ashita v4 runtime evidence received**.
Foundation: [PR #663](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/663).
First recorded: 2026-10-07. Dated entries below record historical progress; consult
the latest milestone for current validation limits.

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
At the #663 foundation milestone these modules were not GUI-wired. Later milestones below integrate replay/UI and experimental addon observations; native process attachment and game controls remain unimplemented.

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


## 2026-10-07 opt-in GET-only projection router
- `src/workbench/runtime/live_client/readonly_api.py`: `create_readonly_router(provider)` exposes only `GET /live-client/read-only/projection`. The host must explicitly register the router and provide previously decoded telemetry; there is no auto-registration, ingestion, discovery or write endpoint.
- Query parameters select client/zone/optional instance; wrong-provider client identity fails closed with HTTP 409, missing observations return 404, and invalid query values are rejected.
- `tests/test_live_client_readonly_api.py` checks projection response, missing client, cross-client guard, query validation and GET-only behavior.
- **Not GUI-integrated:** this is a registration-ready backend seam, not a running toolkit route. Next: opt-in GUI registration with a user-selected feed, test against actual template/viewer conventions, then overlay wiring. CI must validate current HEAD first.


## 2026-10-07 multi-client replay selection foundation
- Added `src/workbench/runtime/live_client/registry.py`: explicit in-memory replay registration, sorted client listing, selected-client frame lookup, cursor advancement, removal and read-only status summaries.
- Multiple replay clients advance independently. Cross-client registration and duplicate IDs fail closed. Registry is not OS client discovery and does not attach to FFXI.
- Added `tests/test_live_client_registry.py` for independent cursors, selection, removal, and invalid registration.
- No changes to global routing or GUI; wire this registry into the optional GET-only API with opt-in viewer presentation in a later slice.
- Current slice still requires CI verification.


## 2026-10-07 opt-in multi-client replay HTTP API
- Added `src/workbench/runtime/live_client/registry_api.py`: explicitly mounted, GET-only `/live-client/replay/clients` and `/live-client/replay/projection` endpoints using `ReplayRegistry`.
- Client list reports read-only session status; selected-client projection returns the validated, zone/instance-filtered player and entity observations. Unknown clients return 404; registered clients with no frame return 409. No client discovery, filesystem access, replay advancement, game writes, or global GUI router mutation.
- Added `tests/test_live_client_registry_api.py` for independent replay clients, selection, unobserved sessions, invalid parameters, and no POST methods.
- The router is **not yet mounted** into the running GUI. Next: coordinate opt-in registration and a player marker with the GUI refactor; afterward prioritize the Windows read-only telemetry bridge.


## 2026-10-08 opt-in replay browser console
- `src/workbench/runtime/live_client/replay_console.py`: self-contained browser page at `GET /live-client/replay/console` showing explicit registered-client selection, read-only status and observed character, zone, XYZ, heading, timestamp and entity count.
- `ReplayRegistry.status()` now includes the selected client's last observed zone so the console can request a zone-scoped projection without assuming a default zone.
- `tests/test_live_client_replay_console.py` covers an explicitly mounted console, no-frame status, selected-client projection, and GET-only behavior.
- **Important:** router is not mounted into the application and is not linked from navigation yet. No actual live client or map overlay; this is a standalone read-only replay console for opt-in integration testing.
- Next: coordinate explicit registration in toolkit GUI and the first map marker; then prioritize Windows-side read-only observation adapter and actual FFXI compatibility validation.


## 2026-10-08 host registration milestone
- The toolkit host now explicitly mounts the replay registry, client listing, viewer projection, and standalone browser console, at `/live-client/replay/console`. Registration uses a new empty in-memory registry.
- Routes remain GET-only. There is **no client process attachment, automatic discovery, user-upload ingest or memory write**, and the console initially says no replay sessions registered.
- `tests/test_live_client_host_registration.py` verifies registration and the absence of non-GET methods on the new endpoints.
- Main toolkit navigation link and controlled replay-import workflow are still pending. Do not imply player position is live without a connected Windows adapter.


## 2026-10-08 opt-in offline replay bootstrap
- `src/workbench/runtime/live_client/bootstrap.py` introduces explicit, validated startup initialization. Set both environment variables `FFXI_LIVE_REPLAY_FILE` (path to a UTF-8 JSON-lines v1 telemetry recording) and `FFXI_LIVE_REPLAY_CLIENT` (exact client ID in those frames) **before starting the toolkit**.
- Startup loads and validates all frames, registers the recording and advances one frame so `/live-client/replay/console` can show its first player observation. The console still has no browser-controlled advancing; remaining frames stay ready for future controlled replay operations.
- If neither variable is set, registration is disabled. Partial or invalid configuration raises an error rather than allowing an ambiguous or malformed data source.
- `tests/test_live_client_bootstrap.py` covers disabled mode, partial configuration rejection, first-frame initialization, duplicate registration and invalid recording isolation.
- The source is offline recording data, **not a real FFXI connection**. No GUI navigation link, Windows reader or game-memory writes have been added.


## 2026-10-08 browser-controlled offline replay progression
- The replay console now has a **Next recorded frame** button. The explicit `POST /live-client/replay/advance?client_id=...` endpoint advances only the registered in-memory recording cursor, returning observed timestamp and zone. It never writes to FFXI, SQL or files.
- Step endpoint requires a same-origin browser Origin header and fails with 403 for cross-origin or missing Origin, 404 for unknown client, and 409 at the end of a recording. It does not upload or ingest new data.
- `tests/test_live_client_replay_step.py` covers these conditions and the console control.
- This makes the replay API no longer literally GET-only: **projection and client listing remain GET-only**, while step is a narrowly scoped replay-state mutation. It is not a game-client control endpoint.
- Next: optional playback timing and player map marker; then prioritize read-only Windows FFXI telemetry adapter and version validation.


## 2026-10-08 bounded local-helper telemetry transport
- Added `src/workbench/runtime/live_client/file_bridge.py`: explicit read-only polling of an operator-provided JSON-lines file with bounded complete-line reads, client identity checks through `TelemetryFeedAdapter`, partial trailing-line tolerance, and fail-closed file-rotation/truncation detection.
- Added `tests/test_live_client_file_bridge.py` covering append/poll, partial frame completion, cross-client rejection, file truncation, and size limits.
- This is **transport groundwork only**, not a Windows process-memory reader or verified real-time FFXI integration. A native/Ashita helper must still be implemented and validated, and a controlled lifecycle needs wiring to the registered live-feed API.
- Do not interpret client-reported version as independent version verification; writes remain unsupported.


## 2026-10-08 Live Client Settings integration
- The existing toolkit `Settings` form now includes a Live Client section. Source may be disabled or offline replay, with persistent recording path, client ID and auto-connect-on-startup checkbox stored via `workbench.runtime.settings_store` in the toolkit settings database.
- The `Validate recording / detect client ID` button POSTs a **local toolkit path** to the same-origin `/live-client/inspect-recording` route. Inspection uses strict bounded v1 JSON-lines decoding and fills the detected client ID only on success. It does not connect to or control the FFXI process.
- Startup prefers explicit paired `FFXI_LIVE_REPLAY_FILE` and `FFXI_LIVE_REPLAY_CLIENT` environment overrides when present; otherwise it uses saved Settings only when replay is selected and automatic restore is enabled. No Windows environment-variable editing is required.
- `tests/test_live_client_settings.py` covers persisted values, optional overrides, disabled auto-connect and recording inspection. Host and Settings template assertions cover wiring.
- The current path input references a file on the toolkit host computer; a browser file-upload/browse control and native live-client source are **not implemented**. Manual replay selection still requires a toolkit restart to restore the configured recording. The UI accurately labels live connection as future work.


## 2026-10-08 browser recording picker
- Settings now supports selecting a local `.jsonl` recording in the browser and importing it through `POST /live-client/upload-recording`. The endpoint is same-origin guarded, limits the file to 16 MiB, validates the strict telemetry schema, and stores only validated recordings in `data/live_client_recordings/` (ignored by Git).
- Successful import fills the managed recording path and detected client ID in Settings. **Save Settings** to persist the choice; enable offline replay and automatic restore to load the first frame on the next toolkit startup.
- `tests/test_live_client_settings_upload.py` covers authorized upload, cross-origin denial, invalid extension/recording, no orphan files, Settings controls and Git exclusion.
- Imported files are local toolkit data, not repository assets. No FFXI process discovery, game-memory read/write, or automatic live-client connection is involved.


## 2026-10-08 read-only telemetry feed registry
- `ReplayRegistry` can now register a `FileTelemetryBridge` per explicit client ID, alongside offline replay sessions. `poll_feed(client_id)` ingests appended, validated JSONL observations and `frame()` / `status()` serve them through existing projection consumers.
- Feed clients cannot use replay `advance()`; status identifies `source: file_feed`. Duplicate client IDs and wrong-client attachment are rejected. Regression coverage: `tests/test_live_client_feed_registry.py`.
- The host has **not** yet been configured to register/poll a file feed, and no native FFXI memory reader exists. The current slice is a reusable registry boundary, not a working live connection.


## 2026-10-08 Settings-managed local telemetry feed
- Settings now offers **Local telemetry file feed (read-only)** with file path, client ID and auto-connect-on-startup. Startup creates a dedicated bounded `FileTelemetryBridge` registration; it does not attach to FFXI memory or scan running clients.
- Replay console has **Poll file feed**, invoking same-origin `POST /live-client/replay/poll-feed`; it accepts up to 100 complete JSONL telemetry frames per click, then refreshes observed location. Regular GET requests do not perform file I/O.
- `tests/test_live_client_feed_settings.py` exercises feed polling, denied cross-origin requests, empty polls, missing clients and Settings/host wiring.
- A local addon/helper still needs to generate the versioned telemetry file; no automatic Windows game process reader is present. Settings changes take effect at toolkit restart.


## 2026-10-08 read-only telemetry producer contract
- `src/workbench/runtime/live_client/producer.py` defines a transport-neutral `ObservationSource.observe()` protocol and a `TelemetryProducer.sample_once()` JSONL writer. It validates the schema/client identity/timestamp before appending a bounded, UTF-8 telemetry frame.
- `tests/test_live_client_producer.py` exercises producer-to-`FileTelemetryBridge` round trips, duplicate timestamp rejection, and wrong-client rejection without creating files.
- The producer is library code, **not a running Windows helper**: no process discovery, memory offsets, memory reading, Ashita/Windower integration, automatic sampling scheduler, or game writes are implemented.
- Next: build a version-verified adapter against an authorized running Windows FFXI instance; integrate the reader's observations into this contract. Preserve the file feed as a safe fallback and use real client testing for offset validation.


## 2026-10-08 Windows executable verification boundary
- Added `src/workbench/runtime/live_client/windows_identity.py`: an explicit SHA-256 allowlist contract for a user-selected Windows client executable; rejects unknown builds, invalid manifests, non-EXE paths and excessively large files.
- Added `tests/test_live_client_windows_identity.py` using synthetic executable fixtures only. No actual FFXI binaries or digests are bundled or approved.
- This is a **prerequisite, not an implemented memory adapter**. Correctly matched on-disk executable identity alone does not verify a running process or memory layout. A future adapter must additionally verify the target process instance, image identity, pointer validity, schema and offset provenance, and fail closed on mismatch.
- No process handles, memory operations, or game writes are present. Actual Windows/FFXI validation is still outstanding.

## Cloud recording sessions and playback controls

- Direct console uploads now receive independent recording session IDs. Recordings containing the same embedded client ID can be loaded together and compared; telemetry identity remains validated against the embedded ID.
- The console supports play/pause, 0.25–4× observed-time playback, one-based frame seeking/timeline scrubbing, previous/restart, replacement and unloading without a restart or Settings edits. Playback pauses when changing sessions or hiding the page, and stops at the end or on request failure.
- Replacement validates the complete candidate before replacing the selected replay. Invalid uploads, missing sessions and attempts to replace a file feed preserve the existing session. Unloading releases the in-memory session; managed uploaded recording files remain available locally.
- Comparison displays each selected recording's observed coordinates, zone and timestamp independently. It does not align time, calibrate coordinates or infer shared instance identity.
- Added dedicated `Live Client Regression` CI with offline API/contracts and a real Chromium console test. Cloud testing uses synthetic telemetry; it does not establish compatibility with Windows or a running FFXI client.
- PR #687 is incorporated into the replay integration branch with review corrections: exact trace bounds, independent zone visits and explicit instance discontinuities. Its remote merge status and GitHub CI remain unconfirmed until GitHub API access is available. Relative X/Z traces do not imply calibrated map transforms.
- Remaining work: shared-shell integration, calibrated map overlays, verified native telemetry adapters and explicitly authorized development controls. No memory offsets, supported client builds or game write capabilities have been added by this milestone.

## Shared Workbench page and native research follow-up

- The host now renders the console inside `workbench_page.html`, with a fluid page width and a Client → Live Client navigation entry. The isolated router keeps its standalone rendering for contract tests.
- Browser regression exercises the shared-shell page, duplicate identities, playback/pause/speed, seek, independent comparison, replacement, unload and segmented X/Z traces. Trace axes use a common scale and do not join zone/instance discontinuities.
- Optional startup-source failures remain visible on the page; opening a recording is independent of Settings. Existing startup configuration remains supported rather than removing users' saved sources.
- [Native source research](LIVE_CLIENT_NATIVE_RESEARCH.md) records immutable upstream revisions, licensing observations and requirements for genuine Windows/FFXI validation. No native build is declared supported and no game write adapter is enabled.

## Experimental framework observation sources

- PR #687 and replay/UI PR #691 are merged. Recorded-session and shared Workbench regression checks passed; Windows/FFXI support remains incomplete.
- `addons/workbench_live/` contains original, explicit-start read-only Ashita v4 and Windower observation exporters with bounded JSONL output. Ashita is the selected real-runtime validation target. No memory offsets, OS process detector, supported-build allowlist or game write functions are provided.
- Lua 5.1 cloud tests exercise actual addon code with synthetic interfaces, JSONL-to-`FileTelemetryBridge` ingestion, identity/zone transitions, invalid fields, missing SDK functions, clock reversal, logout/unload and independent sources. They do not establish real-client compatibility.
- [Addon installation and Windows acceptance procedure](../../addons/workbench_live/README.md) distinguishes cloud JSONL upload from same-host live file-feed testing. Verify the actual Ashita major version and framework/game/module identity before claiming support.

## Authorized Ashita recording and raw-coordinate trace planes

- After the PR #698 conditional entity-zone correction, the user reported successful
  recording and supplied a 121-frame, 120-second capture in zone 50. Every frame
  passed the strict loader and file-feed decoder; 35 frames observe eight distinct
  selected targets. This is real source evidence rather than a synthetic SDK run.
- An anonymized regression fixture preserves all coordinates, headings and target
  transitions while replacing names/indices and shifting timestamps. Tests cover
  replay seeking/rewinding, bounded polling, target observations and Chromium UI.
- The console exposes raw X/Y, X/Z and Y/Z trace planes, with a per-session choice
  and an initial X/Y view for the experimental Ashita source. It preserves numeric
  data, uniform scale and zone/instance segment boundaries. Source and reported
  client version are displayed; entity details keep unknown server IDs explicit.
- The user reported game version `30191204_1`, stairs traversal and no zone change.
  Subsequently supplied Ashita-cli.exe/Ashita.dll report PE version `4.0.0.2`;
  hashes are retained as supplied-file evidence, not running-process verification. Next
  acceptance evidence: verified build identity, zone/logout and
  reconnect behavior, concurrent-client isolation, independent axis/heading
  verification and same-host polling. Calibrated map overlays, automatic process
  discovery and writable development actions remain incomplete.

## Read-only observation downloads

- Enter a waypoint name and use **Download player waypoint**, or **Download
  waypoint** on an observed entity row, to capture the current raw observation
  as a portable `live_client_waypoints` JSON document. Downloads include source,
  reported version, session/client identity and observation provenance; unknown
  server IDs remain unknown. Names are required and bounded to 200 characters.
- **Download path to current frame** exports every recorded sample up to the
  current replay cursor (at most 10,000), preserving numeric position/heading,
  timestamps, zone IDs, client identity and per-frame instance hints. It does not
  export the downsampled display trace or future frames. Seek backward for a prefix.
- GET-only download routes reject missing/unobserved sessions and targets absent
  from the current frame. File feeds can provide a latest-observation waypoint,
  but cannot export historical paths. Downloading pauses browser playback and
  does not advance the source, modify host files, change SQL or command the game.
- The existing portable waypoint/path parsers accept these documents. Persistent
  waypoint library management is described below; calibrated Zone Editor placement, writable warp/
  speed controls and live network transport are still separate development work.
- Runtime-backed API and real Chromium tests exercise player/target/path downloads,
  source isolation, raw values, cursor preservation and zone/instance metadata.

## Runtime report and Windows test-agent handoff

- `python -m workbench.runtime.live_client.runtime_report` produces bounded JSON
  evidence from a strict immutable recording snapshot, with matching SHA-256,
  frame cadence, per-zone raw axis ranges, target counts and context transitions.
  Optional EXE/DLL inputs add PE version resources and hashes using pefile, without
  executing/loading binaries. Existing output reports are not overwritten.
- Supplied Ashita files report `4.0.0.2`; derived metadata is tracked separately
  from the anonymized capture. No binary, supported-build allowlist or new memory
  adapter is added. Running identity, lifecycle and coordinate calibration remain
  unverified until the corresponding acceptance evidence is reviewed.
- [Windows/Codex test handoff](LIVE_CLIENT_WINDOWS_HANDOFF.md) explains local CLI
  access, report generation and remaining zone/logout/multiple-client tests.
  Local Codex is a separate session; this cloud chat has no Windows remote shell.

## Persistent waypoint library

- **Save player to library** and entity-row **Save to library** capture the current
  named raw observation without moving the client or advancing playback. Capture
  retains source/session/client identity, observed timestamp, instance hint and
  unknown server identity. Browser playback pauses before capture.
- The Live Client page lists saved waypoints, with case-insensitive name search
  and an optional zone filter. Rename or delete individual entries; duplicate
  names/coordinates remain independent entries. Unknown instance hints stay unknown.
- Download the whole library as portable `live_client_waypoints` JSON. Import
  that document or a previously downloaded player/target waypoint to append
  validated entries. All rows are validated before insertion; malformed imports
  and capacity failures preserve the current library. Empty imports are a no-op.
- Toolkit persistence lives in the ignored `data/live_client_waypoints/library.db`,
  separate from server SQL and the main toolkit database. It survives page reload,
  recording unload and host restart. SQLite transactions serialize concurrent
  mutations. GET on a new library does not create storage.
- Limits: 1 MiB per uploaded JSON document, at most 1,000 stored points, 200-character
  names/source labels, finite numeric raw positions and integer zone IDs. Imported
  provenance is filtered and never promotes version or coordinate verification.
- Mutations require same-origin browser requests; absent observations/targets and
  storage errors produce useful errors. Corrupt storage is not reset automatically.
  Library data never becomes a supported-build allowlist, warp destination action,
  calibrated map overlay or implicit Zone Editor mutation.
- Runtime-backed API tests and real Chromium validate capture, persistence, filters,
  rename/delete, portable round-trips, invalid-import isolation and origin guards.
  Actual Windows lifecycle tests remain deferred; local Codex is not required.

## Raw waypoint comparison

Choose a saved waypoint in the movement trace to see straight-line 3D distance
and XYZ differences from the current observation. Enable **Show waypoints** to
plot up to 100 comparable points, with a dashed difference line for the selected
point. XY, XZ and YZ views preserve raw coordinates; units, instance identity,
map transforms and navigable routes remain unverified. No movement is issued.

Comparison requires the same recording session, source adapter, embedded client
identity, reported version, zone, instance hint and recorded visit segment. A
return to a zone starts a separate segment even when its instance hint is unknown.
Recordings with identical client IDs remain separate. Capture now stores the
recorded frame and visit segment; older imports remain manageable but must be
recaptured for comparison. Unload/reload creates a new session and excludes saved
points from the previous session. File-feed captures remain supported, but their
visit context is unknown, so they are excluded from this recording comparison.

The read-only `/live-client/waypoints/relative` API reports comparable points and
exclusion reasons. It rejects stale observation timestamps and context changes
during capture/comparison; the browser suppresses overlays when the trace cursor
has changed. Numeric differences outside the finite range are excluded. Tests
use the supplied anonymized Ashita recording, synthetic return visits, duplicate
client IDs and Chromium. These checks do not validate Windows client lifecycle,
coordinate calibration or game writes.

## 2026-10-08 reference audit and implementation decision

[Tako / Clipper reference audit](LIVE_CLIENT_REFERENCE_AUDIT.md) reconciles current
capabilities, pinned sources, Clipper GPL/LGPL discrepancy and unavailable archives.
Prefer bounded Ashita loaded-entity observations next, followed by runtime identity
and transform evidence. Existing replay/library work is reused. Native controls,
calibrated overlays, editor placement callbacks and live navmesh validation remain
incomplete; no old signature profile or historical map count establishes support.
