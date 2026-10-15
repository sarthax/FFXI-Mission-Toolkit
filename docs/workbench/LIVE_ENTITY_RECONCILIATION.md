# Source-backed live entity ID reconciliation (foundation)

The read-only `entity_live_reconciliation.reconcile_reported_id` adapter accepts an explicitly **reported** live `server_entity_id`, zone and selected DSP/LSB index source. It checks exact-ID matches across indexed NPC and mob records and returns `exact`, `ambiguous`, `no_match`, or `unavailable` with typed, named source evidence.

**Identity and confidence boundaries**

- Ashita `client_index` is an ephemeral slot and must never be passed as a fallback for a missing reported server ID.
- `exact` means a single indexed row matches the reported number in the selected zone; it does not establish a runtime spawn, actor type, or instance identity.
- `ambiguous` flags duplicate rows or cross-table collisions without arbitrarily selecting one.
- `no_match` means no indexed row; it is not proof of a missing game entity. An incomplete source/schema returns `unavailable`.
- Mob zone decoding uses the existing zone-database encoded-ID convention. Instance/nonstandard allocation needs independent capture/SQL validation.
- This helper reads an existing SQLite database in read-only mode. It does not write to Data Gaps or alter the live bridge, map, or server.

**Next integration:** surface selected source, evidence coverage and match status in the existing unified viewer inspector via a bounded server-side lookup/API. Do not run per-frame database queries, infer types from unverified raw Ashita enums, or silently promote capture-derived map rows to server configuration.
