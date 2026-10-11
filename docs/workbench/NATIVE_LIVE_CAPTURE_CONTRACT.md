# Native Live Capture — Read-only Contract Foundation

**Status:** proposed envelope and tests; not connected to native plugin, bridge, or GUI.

## Existing implementation found on main

- `addons/workbench_live/workbench_live_ashita.lua` registers `packet_in` and `packet_out`.
- `addons/workbench_live/workbench_packets.lua` records a restricted `event_emote` profile to JSONL, with 10 observations/second, 10,000-row and 4 MiB safeguards; it currently performs synchronous file writes/flushes in the callback.
- `src/workbench/captures/ashita_packet_ingest.py` validates that existing experimental schema and imports it into canonical raw capture rows.
- The existing recorder's event_emote format **is not** the new transport envelope. Do not silently change its schema or import semantics.

## New independent contract

`src/workbench/captures/live_capture_contract.py` defines a strict, versioned, transport-independent packet envelope and per-client/session sequence checker. It is deliberately not wired to live packet callbacks yet.

Required fields: `schema_version`, `client_id`, `session_id`, `sequence`, `observed_at_ns`, `direction`, `opcode`, `raw_hex`, `is_injected`, `is_blocked`. Optional cumulative `dropped_before`.

The envelope preserves raw packet bytes and hook flags, and enforces explicit size, type, sequence, timestamp and cumulative drop rules. This contract does **not** establish wire-level provenance or decode packet semantics.

## Next larger slice

1. Inventory existing Capture canonical tables and session lifecycle; map this envelope to existing rows without creating a duplicate store.
2. Replace callback-time disk flushing with a bounded, nonblocking native queue and explicit loss reporting. Keep the existing experimental export behavior until parity tests pass.
3. Add crash-safe spool/transport and per-client session health. Explicitly handle disconnect and zoning.
4. Extend the current Ashita ingestion adapter or add a versioned adapter for the new envelope; verify raw-byte and source-reference parity.
5. Add a GUI recorder session page using existing Capture routes.

Keep this work independent of the ongoing Ashita movement-write DLL branch.

## 2026-10-11 implementation progress

- New native envelope format is auto-detected by the existing Capture single-file uploader, bundled-source scan and source rebuild path; legacy `ashita_packets` remains supported unchanged.
- Offline native JSONL ingestion writes into `capture_raw_packets` and source row locators with transactional rollback. Tests cover provenance, malformed input and upload discovery.
- `live_capture_spool.py` provides a **backend reference implementation** of a bounded offer queue, explicit reject counters, worker-driven fsync and exclusive segment creation. It is not yet attached to Ashita callbacks or the Live Bridge.
- **Known integration gap:** rotated spool segments after the first start at sequence >1, whereas the current standalone JSONL importer requires sequence 1. Implement a versioned session manifest and multi-segment import before enabling rotation in the live recorder. Never reset sequence silently.
- **Known integration gap:** the spool is not thread-safe; native producer/consumer synchronization and shutdown semantics require an explicit implementation. This Python reference is not a drop-in native C++ queue.
- **Known integration gap:** queue rejections are counted, but the native producer must report loss through the cumulative `dropped_before` counter, including when no subsequent packet arrives. Add a session-end summary and reconciliation before declaring loss accounting complete.
- **Known integration gap:** source identity, timestamps, hook-stage provenance and exact native callback bytes require validation against the running Ashita v4 plugin.
- **Validation:** changes committed but tests/CI and Windows live-client testing are not yet verified. Do not label this production-ready.

## Queue and loss contract update

- A gap in packet sequence numbers is permitted only if it is exactly explained by the increase in `dropped_before` since the previous accepted observation. Duplicate or reversed sequence numbers remain invalid.
- Producer offers are nonblocking under lock contention; a rejected offer is a source-side loss and must advance the producer sequence and cumulative loss count. The Python spool does **not** generate those producer counters.
- Worker disk operations do not hold the queue lock. Failed writes retain the pending queue item and fault the spool rather than silently discarding it.
- This reference implementation has no background worker, no session-end manifest, no cross-segment continuity proof, and no native callback integration. A source that terminates immediately after a drop cannot yet prove its final loss count.
- The existing parser still requires standalone sessions to start at sequence 1; later rotated segments are not independently importable until the session manifest / segment-aware importer is implemented.
