# Native Live Capture — AIO Recorder Plan

**Status:** proposed roadmap; not implemented  
**Date:** 2026-10-11  
**Related research:** [Live Client third-party control research](LIVE_CLIENT_THIRD_PARTY_CONTROL_RESEARCH.md)

## Goal

Turn the existing read-only Ashita v4 native plugin into a first-party, multi-client, loss-aware live observation source for the existing Toolkit Capture, packet decoder, entity research and spatial viewers. Preserve the existing capture importers and network-level PCAP/PCAPNG support for historical data and streams not visible to the Ashita callbacks.

**Non-goals for the first milestone:** movement writes, packet injection, packet blocking, replacing existing capture databases, or claiming visibility into all network traffic.

## Architecture boundary

`FFXI/Ashita native callback → bounded nonblocking event queue → authenticated local transport → Toolkit canonical capture adapter → existing capture index/decoder/replay → research modules`.

Capture must be resilient to a disconnected GUI: explicitly select bounded local spooling or stop-with-visible-error. Never silently discard packets. Do not perform blocking disk/network I/O in Ashita packet callbacks.

## Phase 0: audit and interface contract

- Inventory existing live-client plugin, bridge transport, capture storage, event schema, importers, replay and UI routes on current `main`.
- Confirm Ashita callback contracts and actual observed packet byte boundaries; preserve raw packet bytes, direction, size, ID, timestamp, chunk ID, injected/blocked provenance where provided.
- Identify overlap with PacketViewer/Packeteer, NPCLogger, ActionView and EventView; implement **adapters**, not parallel storage or competing GUI pages.
- Define per-client/session IDs, versioned schema, clock/sequence behavior, queue capacity, backpressure, spool retention, crash recovery, privacy controls, and transport authentication.

## Phase 1: passive packet recorder (first deliverable)

- Read-only `packet_in` and `packet_out` capture, explicitly enabled per client.
- Loss-aware bounded queue, source-side monotonic sequence, timestamps, queue depth and drop counters.
- Versioned, portable session artifact with raw packet payloads plus minimal metadata; no fabricated packet semantics.
- Reuse canonical ingestion and existing packet decoder for live or completed sessions.
- Start/stop/session health controls in the Live Client / Capture workspace, not an unrelated second application.
- Tests: known packet fixture parity; zone transitions; disconnect/reconnect; burst load; backpressure; multi-client isolation; no packet mutation.

**Acceptance:** record a short session, export/import it through existing Capture, decode the same packet bytes and preserve exact ordering and loss diagnostics. Disconnecting the browser must not silently corrupt the session.

## Phase 2: unified event recorder

- Add passive entity appearance/position/despawn; action actor/target and start/finish; job/status/buff; NPC/menu/CSID observations where evidenced.
- Correlate decoded events to their raw packet source and entity IDs. Mark unknown and inferred values explicitly.
- Provide a synchronized event timeline alongside packet view, 2D/3D viewer, Entity Browser and Feature Trace.
- Validate against real DSP capture fixtures and server SQL/Lua sources.

## Phase 3: recording UX and research automation

- Multi-client recording controls, session metadata, filters, bookmarks, replay, export, and capture-health panel.
- Trigger rules for **passive** bookmarks on zone, NPC, CSID, battle and packet anomalies. Active packet requests require separate write authorization.
- Support existing historical file imports and optional PCAP/PCAPNG capture in parallel; do not mislabel Ashita callback packets as network-level captures.

## Explicit separation from write-control milestone

Movement, follow, target changes, NPC/menu automation and ScanZone-style active requests require a separately gated write-capable adapter, operator approval and DSP-only validation. Read-only capture must function without any write permissions.

## Proposed PR slices

1. **Recon + schema**: capture/live-client interface map, session envelope specification, fixtures, and no-op adapter test.
2. **Recorder backend**: canonical ingestion and portable session format with parity tests.
3. **Native source**: callback-to-queue event transport, diagnostics and isolated per-client sessions.
4. **GUI**: start/stop, health, timeline and existing Capture navigation.
5. **Enrichment**: passive entity/action/status decoders and cross-module correlation.

Each PR should remain small enough for CI and avoid concurrent Ashita movement-DLL changes by first defining the transport contract and integration tests in Python/backend.

## Success metrics

- Exact raw packet byte preservation for known fixtures.
- Measured loss/drop counts, queue depth, end-to-end latency and time alignment.
- No observed packet mutation or unintended writes.
- Recovery behavior documented for zone changes, crashes, reconnections and multiple clients.
- Session readable by existing Capture tools, with cross-links into Entity, Zone Editor, Feature Trace and Packet Viewer.

**Decision:** Treat this as a first-party Live Capture source **within** the current Capture platform, not a wholesale replacement of capture tooling.
