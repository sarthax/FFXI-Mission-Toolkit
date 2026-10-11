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
