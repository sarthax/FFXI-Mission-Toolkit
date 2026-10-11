# Live Client — remaining delivery roadmap

Status baseline: 2026-10-10. Authoritative implementation ledger: [ROADMAP_CURRENT.md](ROADMAP_CURRENT.md). Architecture: [LIVE_CLIENT_BRIDGE.md](LIVE_CLIENT_BRIDGE.md), [LIVE_CLIENT_REFERENCE_AUDIT.md](LIVE_CLIENT_REFERENCE_AUDIT.md), [LIVE_CLIENT_WINDOWS_HANDOFF.md](LIVE_CLIENT_WINDOWS_HANDOFF.md).

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

### P2 — Real bidirectional transport (safe simulation first)

**B6. Versioned command protocol:** Extend the existing bridge rather than creating a second server. Define selected source/client/session generation, request UUID/sequence, capability advertisement, heartbeat, expiration, ack/reject/error, timeout/retry (idempotent commands only), bounded queues and audit log. Prioritize STOP independently of high-volume Capture streams. Keep replay/Windower/read-only providers incapable of writes.

**B7. UI operator controls:** Show selected authorized client, runtime/build status, *read-only / simulated / explicitly writable* modes, last command and readback, arm/disarm, emergency stop and reconnect state. Default disarmed after every restart, zone transition, identity change or loss of liveness; enforce safeguards server-side, not just in UI.

**Acceptance:** Two-client synthetic tests show that commands cannot cross identities/zones, timed-out or stale requests cannot execute later, STOP remains available under overload, and reconnect disarms. Windows loopback latency measured without enabling actual game writes.

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
