# Live Client — delivery roadmap and acceptance ledger

Status baseline: 2026-10-10. Authoritative implementation ledger: [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md). Architecture: [LIVE_CLIENT_BRIDGE.md](LIVE_CLIENT_BRIDGE.md), [LIVE_CLIENT_REFERENCE_AUDIT.md](LIVE_CLIENT_REFERENCE_AUDIT.md), [LIVE_CLIENT_WINDOWS_HANDOFF.md](LIVE_CLIENT_WINDOWS_HANDOFF.md).

## Current movement capability audit — 2026-10-11 (supersedes older historical gates below)

**User-reported live milestone:** The native Ashita DLL, Toolkit Live Client and 3D Zone Viewer now support actual movement and have been merged to `main`. The repository confirms implemented native movement handlers and UI controls; this documentation pass did **not** independently replay the live Windows test. Historical sections below saying native writes do not exist refer to earlier development stages and are **not the current product status**.

| Original goal | Current implementation / evidence | Audit |
|---|---|---|
| Ashita client observation and native XYZ | Authenticated live Lua bridge plus native plugin XYZ getter; operator's zone-98 native/Lua sample agreed within 0.0006 units at 23 ms separation | **Met for tested client** |
| Native player movement | Native movement adapter with `autorun`, local XYZ setters, experimental warp pointer mode, and explicit native control handler; in-game autorun short legs recorded in prior milestone | **Implemented; user reports working** |
| Toolkit-originated commands | Native file channel `settings.ini` / `command.txt` / `status.txt`, opt-in enable/disable, nonce, sequence, freshness and audit outcome; `src/workbench/runtime/live_client/native_control.py` API | **Implemented; user reports tested** |
| 3D Viewer movement | Warp controls: arm, disarm, STOP, compass/diagonal nudges, direct coordinates, navmesh-target picking, bookmarks, speed, zone guard, pending cross-zone bookmark | **Implemented; user reports integrated** |
| Stop, disarm and defensive validation | Movement adapter, command channel and viewer guards, independent per-load nonce, audit ring, identity/zone checks; `server_confirmed=false` remains explicit | **Implemented; lifecycle stress tests pending** |
| 2D destination movement / path-follow | Core path/waypoint and 2D research tools exist, but this audit did not establish an equivalent end-to-end, directed 2D-map action or autonomous route traversal with obstacles | **Partial / separate target** |
| Server-authoritative proof | Native acknowledgments are client-local; record independent DSP/Topaz `!logpos` before/after, walk/no-snapback, zone and relog trials | **Not independently established in repository** |
| Unified passive capture | Bounded Ashita packet observer and canonical ingest foundation; roadmap's full high-volume capture and event/entity lifecycle enrichment remain separate | **Partial / ongoing** |
| Windows recovery, dual-client isolation, spatial calibration | Synthetic coverage and some Windows observations; repeatable two-client, reconnect, unknown-zone/instance and multi-zone landmark results are not comprehensively documented | **Partial / acceptance backlog** |

**Important safety/portability findings:** `auto_arm=warp`, `enable_ttl_seconds=0` and file-command opt-in are available as development conveniences, but reduce the default-off posture when configured. The `DEV-SERVER-ONLY` literal is **not** a server-attestation check. The experimental warp-pointer offsets are version-dependent; do not assume they work on other client builds. Speed percentage mapping and server tolerance require measured confirmation. The UI's snap-to-navmesh is optional and does not establish safe collision/grounding for arbitrary coordinates.

**Residual high-priority acceptance:** (1) Record a reproducible DSP server-side position test with before/after server and native XYZ, (2) verify STOP/disarm and zoning/logoff/reload recovery, (3) test two distinct live clients and session isolation, (4) add explicit private-server allowlisting/version compatibility where feasible, (5) verify speed/warp consistency and movement audit data, (6) complete capture-event stream integration. The original *native controlled movement and 3D Viewer integration* milestones should no longer be shown as unimplemented.

## Goal and what is **not** delivered

The end goal is an authorized local development/testing client that can **observe**, **safely control** a live FFXI player toward a Toolkit-selected destination, and **capture** correlatable evidence into the existing Capture system. Replaying a path or moving a browser camera does not count as game-character movement.

Available foundations include Ashita bounded observations and recordings, playback, partial zone recovery, selected entity/inventory data, passive packet samples, canonical Capture import, research links, 2D trace/waypoint tools, and a read-only 3D Zone Viewer with primary and multiple secondary client markers, interpolation, headings, camera following, nearby-entity picker/click/hover/inspection and research handoffs. PRs #947, #948 and #957 merged 2026-10-10. The DXT1 cutout correction and diagnostic force-opaque tool still require real-DAT visual verification; do not mark Bastok floors resolved.

**Not yet demonstrated:** production-quality simultaneous Windows client observation and recovery; validated coordinate/map calibration; a verified native standalone adapter; a version-checked, authorized *game movement* write; comprehensive capture packet fidelity; complete client-entity identities; end-to-end destination → actual movement → evidence.

### Status vocabulary

- **Implemented / cloud-tested**: code exists and synthetic or browser tests pass; does not establish live-client compatibility.
- **Observed on Windows**: a named build/runtime, client, zone and reproducible recording were tested.
- **Verified in-game**: observed game state and independent server/client readback confirm intended effect.
- **Blocked / conditional**: requires real Windows test artifacts, source API verification, safety authorization, or license review.

## Delivery batches (prioritized; target one cohesive PR per batch)

### P0 — Baseline, CI and Windows smoke suite

**B1. Viewer and telemetry acceptance:** Exercise primary/secondary live clients, switching selected client, marker hover/click, selection across polling, follow and stop, lost clients, restart, zone change and fast polling; verify correct heading and stale-data removal. Validate PR #947 DXT1 cutouts in Sauromugue Champaign [S] and #948 forced-opaque comparison in Bastok independently; texture verification is a separate track.

**B2. Reproducible matrix and diagnostics:** Record Ashita version, loaded game executable/module signatures, adapter capability, active server, zone/instance, clock basis and stream generation. Provide a one-click export of redacted debug/status and bounded observation/packet samples; never include credentials or memory dumps by default.

**Acceptance:** A repeatable Windows checklist and anonymized artifacts from at least one DSP/Topaz client and two concurrent clients; synthetic CI plus browser smoke checks. Explicitly mark failed, skipped or unavailable gates. No write enablement.

### P1 — Reliable observations and identity

**B3. Runtime lifecycle:** Test ordinary game startup, zoning, long transitions, logout/relogin, zone mismatch, reconnect, stale socket/file producer and process replacement. Distinguish loading from disconnect; reject old session generations; preserve gap/drop indicators rather than smoothing away missing evidence.

**B4. Entity identity:** Verify reported server ID against DSP/Topaz catalog and target behavior, distinguish client index/slot from ID, detect recycled slots, duplicate names, zones/instances and inventory caps. Record unknown and ambiguous identity without making a trusted join.

**B5. Spatial calibration:** Compare sampled game XYZ/heading to 2D map, 3D mesh, live markers and Zone Editor offsets in multiple known landmarks/zones. Store sourced zone-specific transform/axis/heading evidence with tolerances and version. Flag uncalibrated views rather than committing positions.

**Acceptance:** Measured rates/gaps, correct rejection of stale samples, sample-linked identity confidence and landmark residuals; all regressions have fixture tests. No floor/navmesh, entity-ID or heading correctness claim based solely on visual proximity.

### Movement control foundation — simulation-only gate

The new `workbench.runtime.live_client.movement_control` service builds on the existing transport-neutral `BridgeEnvelope` and `BridgeMailbox`. It validates finite XYZ, same selected client/session/generation/zone, bounded nudge size, explicit simulation consent, fresh monotonic telemetry, and local STOP/disarm. Its response is **always REJECT / writes_not_supported**. This is an isolated testable control contract, **not** an active endpoint, Ashita memory writer, packet injector, or real in-game movement mechanism. Next: wire a local bridge command transport and verify the Ashita v4 capability with an authorized Windows environment before enabling actual writes.

### Command preview HTTP milestone

The opt-in local bridge now exposes `GET /live-client/bridge/movement/capabilities` and same-origin `POST /live-client/bridge/movement/simulate`. The POST requires an explicitly provisioned, connected client, matching zone and consent; it runs through the existing reject-only movement gate and returns `executed:false`. It is **not** a bidirectional Ashita command receiver, does not write memory/inject packets, and does not arm real game controls. The remaining critical next step is a versioned authenticated bridge response channel and verified Ashita v4 adapter.

### Authenticated control delivery milestone

A read-only `capabilities_probe` now travels from a same-origin Toolkit request to the selected authenticated Ashita peer on its next `/wblive bridge ping`. The addon returns a matched `REJECT` indicating game writes are unsupported. The shared control broker isolates client/session/generation, bounds the queue to one outstanding probe per client, expires unsent requests, and cancels on receiver shutdown or credential rotation. API status reports queued/delivered/rejected/expired without exposing secrets. This verifies a *command envelope round-trip*, not execution of a player movement command. Only the fixed capability probe is dispatchable; movement and STOP commands remain undelivered until adapter verification.

### P2 — Real bidirectional transport (safe simulation first)

**B6. Versioned command protocol:** Extend the existing bridge rather than creating a second server. Define selected source/client/session generation, request UUID/sequence, capability advertisement, heartbeat, expiration, ack/reject/error, timeout/retry (idempotent commands only), bounded queues and audit log. Prioritize STOP independently of high-volume Capture streams. Keep replay/Windower/read-only providers incapable of writes.

**B7. UI operator controls:** Show selected authorized client, runtime/build status, *read-only / simulated / explicitly writable* modes, last command and readback, arm/disarm, emergency stop and reconnect state. Default disarmed after every restart, zone transition, identity change or loss of liveness; enforce safeguards server-side, not just in UI.

**Acceptance:** Two-client synthetic tests show that commands cannot cross identities/zones, timed-out or stale requests cannot execute later, STOP remains available under overload, and reconnect disarms. Windows loopback latency measured without enabling actual game writes.

Ashita v4 source-only capability audit: `/wblive movement audit` checks available Lua method names without executing writes, reading addresses or modifying outgoing packets. Windows results remain pending; method presence is not permission or verified functionality.

Native plugin feasibility slice: `native/ashita_workbench_probe` provides an original **read-only** Ashita v4 C++ `IPlugin` with documented ABI exports, Win32/x86 CMake configuration, and in-game `/wbprobe` load test. It is source-tested in CI; actual DLL compilation, Ashita loading and client runtime verification require the user's Windows SDK environment. Position writes and packet injection remain disabled. The prior Lua audit showed `GetWarpPointer` and `SetPosition` not exposed in its sampled interfaces, and candidate outgoing-packet method presence alone does not establish a movement-capable interface.

Windows native-position acceptance confirmed (2026-10-11): Ashita v4.05 Beta and VS 18 x86/C++20 built and loaded the plugin; `/wbprobe position` reported changing XYZ values in zone 98 for entity 1024. Beta SDK lacks `GetEntityIndexById`, so the native reader performs a bounded server-ID scan. This validates native readback only. Next: compare against Lua telemetry, then audit supported native setters and DSP/Topaz acceptance before arming writes.

### P3 — First authorized movement action (explicit go/no-go)

**B8. Capability feasibility:** Verify an Ashita v4-supported command API against actual installed version, or document why a narrowly scoped native Windows adapter is needed. Audit Project Tako/Clipper reference behavior and licenses; do not copy incompatible code. Require test client/environment ownership, exact build identity and opt-in authorization.

**B9. Bounded live movement:** Implement one development-only small nudge or supported position action, with allowed zone/state/coordinate bounds, instant STOP, audit, source identity and independent readback. Reject unsupported/unknown build, busy zoning, no position, different client/session, disconnected bridge and invalid destination. Never infer server acceptance from a local coordinate write.

**Acceptance:** In a controlled DSP/Topaz session, the *actual game character* moves by the requested bounded amount; live observations and independent server/game-side state are reconciled; rejection/correction documented. Failure automatically disables control. This gate is mandatory before any route automation.

### P4 — Assisted destination navigation

**B10. Navigation intent:** Select destination from 2D/3D map, existing waypoint library or grounded entity; expose exact game XYZ, zone, transform source, tolerance and origin. Preview route and collision/navmesh evidence. Treat missing or inconsistent transforms/navmesh as a block rather than guessing.

**B11. Feedback travel:** Implement stepwise, cancellable progress using fresh player position/heading feedback, speed limits, obstacle/stuck/rejection handling, zone/instance guards, pause/resume and restore of prior control state. No blind file-path playback masquerading as real control.

**Acceptance:** Measured successful and failed routes in an authorized test zone; STOP works while moving, mismatch triggers halt, progress and readback remain visible and auditable. Zone changes require explicit new authorization.

### P5 — Capture and research feedback loop

**B12. Producer profiles:** Reuse Ashita and other *verified* producers for event/CSID, target interactions, mob state, movement, action/battle and packet observations according to actual interfaces. Record original bytes, direction, hook stage, timestamps and timebase, sequence, dropped counts, producer/build identity and source hash. Separate capability-supported profiles from proposed profiles.

**B13. Canonical Capture ingestion:** Send bounded streams/recordings to existing Capture ingestion and decoder, not new competing packet storage. Validate equivalence against independent packet data on Windows, avoid assuming packet hook bytes are on-wire bytes, and expose source/zone/time/ID provenance and uncertainty.

**B14. Research session workflow:** A selected test session can Locate → (authorized) Move → Observe/Record → Inspect relevant Capture/CSID/Feature Trace/Entity dossier with exact evidence locators. Show candidate/ambiguous joins explicitly and never auto-write SQL.

**Acceptance:** Reproduce an NPC interaction with synchronized player/entity observations plus reviewed capture packets; sources and gaps visible and no unverified causal/ID inference.

### P6 — Hardening and optional advanced scope

**B15. Fault/load matrix:** Test two clients, logout/relogin, packet overload, high-frequency telemetry, zone transitions, process replacement, unsupported builds, lost STOP acknowledgment and crashed addon/receiver. Establish memory/CPU and buffer limits; preserve original evidence despite throttling.

**B16. Additional observations:** Evaluate animation/subanimation, appearance, status/equipment, inventory and party-state probes only where documented APIs and provenance support them; prioritize research/Feature Trace value.

**B17. Advanced developer controls:** Independently assess collision, speed/elevation and temporary placement/return only *after* B9–B11; each requires explicit support, authorization, safety bounds, deterministic restore/readback, separate kill switch and server correction review. A desired capability is not an implementation commitment.

**Acceptance:** Documented compatibility matrix with explicit unsupported features, clean teardown and independently repeatable Windows evidence. No silent escalation of write privilege.

## Work order, dependencies and parallel tracks

- **Immediately executable cloud slices:** B1's browser/regression harness, B2 exporter specification, B3/B4 fixture and report extensions, B6 simulator and command-state tests, B12 source profile inventory.
- **Needs Windows session samples:** B1 complete signoff, B2 loaded-build identity, B3 lifecycle, B4 catalog IDs, B5 coordinate calibration, B13 packet fidelity.
- **Requires separately authorized go/no-go:** B8/B9 real movement and all dependent B10/B11/B14 movement steps, B17 optional controls.
- **Parallel, nonblocking texture track:** Verify DXT1 vegetation and Bastok force-opaque diagnostics; do not couple mesh rendering fixes to movement/capture milestones.
- **Do not duplicate modules:** Existing Capture, Feature Trace, Zone Editor, Entity and Wiki remain source-of-truth surfaces; viewer navigation/inspection is read-only.

## Operator deliverables and review discipline

Each batch should ship tests, updated Toolkit help and this roadmap, source/adapter versions, redacted test samples where available, compatibility gate outcomes and a clear distinction among simulated, observed and verified-in-game. Prefer one coherent PR per batch with green CI; avoid long-lived stacks against moving main. Do not auto-merge unrelated agents' branches or reinterpret an unverified working branch as green.

### Native XYZ comparison dashboard (2026-10-11)

Direct Live Bridge now offers a **Native XYZ comparison (read-only)** section. With native probe loaded, run `/wbprobe position`, paste the chat line, and immediately compare against the selected client’s current live snapshot. The same-origin API rejects disconnected clients, stale telemetry and zone mismatch, and reports XYZ distance. This is a manual operator diagnostic and **not** a native streaming adapter, movement control, or independent server-side validation. Compare while stationary to avoid timestamp uncertainty.

### Native XYZ setter signature gate (2026-10-11)

Ashita v4-Beta public SDK `IEntity` declares `SetLocalPositionX/Y/Z(uint32_t, float) const`. The native plugin now performs compile-time signature checks and provides `/wbprobe capabilities` to report setter declaration availability. **This does not invoke a setter, establish runtime permission, or demonstrate server-accepted movement.** Confirm compilation against the installed `C:\\ValhallaXI\\Ashitav4-Beta\\plugins\\sdk` headers, then test the diagnostic on the authorized DSP test client. The existing XYZ reader and Lua telemetry comparison remain read-only.


### Native movement adapter implemented, NOT live-tested (2026-10-11)

B9 groundwork: `native/ashita_workbench_probe/movement_adapter.h` adds a fail-closed, SDK-independent movement policy (disabled by default, consent token, character+zone binding, bounded 3-yalm steps, 1 s rate limit, duplicate/busy/zoning/stale rejection, unconditional STOP, audit ring) with an `autorun` (IAutoFollow, experimental) and a `local` (SetLocalPosition) executor. Verified: installed-SDK x86 build (C++20), dumpbin x86 + 3 exports, host-compiled policy tests (/W4 /WX). **Unverified:** any in-game effect, axis meaning of IAutoFollow deltas, packet emission, server acceptance. Outcomes always report `server_confirmed=NO`. Toolkit-side command wiring (Live Client -> `/wbprobe`) is the next slice; the manual smoke test is in the native README.

## Update 2026-10-11: autorun live result and Tako/warp mode
- Autorun live-tested on the dev server: 1-yalm legs arrive (reason `arrived`), no rubber-banding observed; server `!logpos` after moves still to be recorded.
- Project Tako analysis and the new experimental `warp` mode (untested): see `PROJECT_TAKO_ANALYSIS.md`.


## Toolkit-driven warp, speed hold and enablement (built 2026-10-11, live test pending)

Status: host-tested only (adapter, control router, Python channel/API). **Not yet live-tested**: large-distance warps,
warps after zoning, speed value mapping, the file channel, and click-to-warp in the viewer.

### Enablement (default OFF, admin opt-in)
- Nothing is armed at load. The in-game `/wbprobe movement enable warp DEV-SERVER-ONLY` path still works.
- Persistent opt-in lives in `<Ashita>/config/workbench_native/settings.ini` (re-read every 2 s, except TTL/base speed which are load-time):
  ```
  allow_file_commands=1      ; lets the Toolkit arm/stop/warp/speed through command.txt
  auto_arm=warp              ; optional: arm at load and re-bind after every zone change (""/warp/autorun/local)
  enable_ttl_seconds=0       ; 0 = never expires (default 120)
  speed_percent=120          ; optional: hold this speed once armed (25..400)
  base_speed=5.0             ; MovementSpeed2 at 100% (verify with /wbprobe speed status)
  ```
- The `DEV-SERVER-ONLY` token is a consent literal only. **There is no server-identity check**: the plugin cannot tell
  a private dev server from any other. An allow-list (zone/server name or host) is the natural next step for other admins.

### Control channel (Toolkit -> plugin)
`config/workbench_native/{settings.ini, command.txt, status.txt}`; flat key=value. The plugin publishes a per-load `nonce`
in `status.txt` (~2 Hz); each command carries `seq` (epoch ms, strictly increasing), `nonce`, `ts_ms` (must be within 15 s),
and, for `enable`, `consent=DEV-SERVER-ONLY`. Commands: `enable`, `disable`, `stop`, `warp_to`, `speed`, `speed_off`.
Every command goes through the same MovementAdapter/SpeedOverride checks as the chat commands (binding, zoning, bounds, audit).
Result fields stay `scope=client_local`, `server_confirmed=NO`.

### Coordinates
Toolkit/viewer/commands use **server order** (what `!logpos` prints: x, y = height, z). The plugin converts once
(`ServerToSdk`: SDK = (x, z, y)). Viewer scene = (x, -y, -z), so server = (sx, -sy, -sz). Server Y is inverted: to raise
the character use a smaller Y (the viewer map-point pick applies a default 0.5 yd lift). Arbitrary map points are not
navmesh-checked: run `!checknav x y z` before treating one as valid.

### Speed override
`MovementSpeed2 = base(5.0) * percent / 100` (mapping unverified; compare with `!speed 120` via `/wbprobe speed status`).
Held at about 4 Hz while armed, so it survives zone changes; restored once on disarm/unload. Whether the server tolerates it is untested.
In game: `/wbprobe speed <25..400>|off|status`, `/wbprobe warp <id> <x> <y> <z>`.

### Live test steps
1. Unload the plugin, copy the new DLL (SHA-256 starts `033d5c3d7bc4c3e9`) over `plugins\workbench_native_probe.dll`, load it.
2. Create `config\workbench_native\settings.ini` with `allow_file_commands=1`.
3. `/wbprobe movement enable warp DEV-SERVER-ONLY`; `!speed 120`; `/wbprobe speed status` -> expect MovementSpeed2 about 6.0.
4. `/wbprobe warp t1 <x> <y> <z>` to a far point (copy from a mob spawn); verify with `!logpos`; walk and confirm no snap-back.
5. Zone and confirm the speed hold re-applies and (with `auto_arm=warp`) the plugin re-arms.
6. Toolkit 3D viewer: open the zone, "Native warp" panel, Arm, tick Pick target, click a spawn, "Warp to target", compare `!logpos`.
7. STOP / Disarm buttons; `/wbprobe movement audit` lists everything.

## Native Unified Capture — milestone (2026-10-11)

**Goal:** An in-house, all-in-one live FFXI capture capability built on the existing Ashita v4 observation adapter and canonical Capture pipeline. Retain PCAP/PCAPNG and historical external-tool importers for wire-level and legacy evidence.

**Existing baseline (do not recreate):** `addons/workbench_live/workbench_live_ashita.lua` already registers `packet_in`/`packet_out` and routes events to `workbench_packets.lua`. That module currently supports only the explicit `event_emote` profile (incoming `0x034`, `0x05A`; outgoing `0x05D`), 10 observations/second, 4 MiB/file, 10,000 observations, and passive original-byte JSONL. It includes rate-drop counts, injected/blocked metadata, telemetry/identity/zone checks and a manual canonical Capture importer. Tests: `tests/test_live_client_ashita_packets.py`. These constraints are intentional; **not** a full-packet capture system yet.

**Increment 1 — foundation, in progress:**
- Preserve read-only, original-byte callback behavior. No injected, blocked or modified packet writes; do not overlap the separate Ashita native DLL movement branch.
- Define a versioned packet envelope and explicit loss/termination semantics that preserve direction, opcode, original payload, packet size, client/session, zone, sequence, hook stage, injected/blocked status, dropped-before, source recording, adapter version, and provenance. Mark hook observations as *not equivalent to wire PCAP*.
- Extend the existing passive sampler incrementally with **opt-in bounded profiles** and robust diagnostics; maintain `event_emote` compatibility and do not enable indiscriminate all-opcode capture by default.
- Implement/verify bounded buffering and flush/backpressure policy before raising sample rates. The current callback writes and flushes synchronously per packet: this must be assessed before enabling sustained capture. Count rate-limit drops separately from queue/full, write failures, invalid packet and context-stop reasons.
- Expand deterministic Lua and Python tests: original vs modified data, injection flags, direction, boundaries, rate/drop counters, reconnect, zone/identity transitions, multi-client isolation and import fidelity.
- Windows Ashita acceptance is required for real callback fidelity and sustained performance; CI alone does not establish it.

**Increment 2 — unified recording:** route existing packet JSONL into canonical Capture ingest with session manifest, indexing and provenance; avoid parallel storage schema.

**Increment 3 — Live Capture UI:** start/stop, profile selection, per-client health and drop metrics, live packet inspection, filters and recorded-session import.

**Increment 4 — enrichment:** correlate packet streams with entity ID/XYZ, targets, action lifecycle, NPC/menu/CSID and cross-client timelines; preserve raw evidence and confidence.

**Acceptance gate:** One client produces an opt-in passive recording that imports losslessly with explicit drop accounting and no gameplay writes. Two simultaneous clients remain isolated. Reproducible Windows performance/overhead measurements precede high-volume modes.

**Research:** [Third-party control and capture audit](LIVE_CLIENT_THIRD_PARTY_CONTROL_RESEARCH.md). **Scope note:** the DLL movement/write work continues independently.
