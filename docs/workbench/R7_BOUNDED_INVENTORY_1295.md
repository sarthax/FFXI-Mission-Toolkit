# R7 #1295 — Bounded persisted inventory v2 (draft)

Endpoint: `GET /api/supervisor/test-character-inventory-v2?charid=...&location=1&cursor=0&limit=100`.
Existing supervisor bearer token and disposable-character allowlist are mandatory. Location is restricted to 0 inventory, 1 Mog Safe and 10 Mog Safe 2. Database credentials must have SELECT-only char_inventory permission; connection remains 127.0.0.1, read-only transaction.

Rows are ordered by slot, with itemId, quantity and opaque base64 extra bytes; absent extra differs from zero bytes. No augment or installed-furnishing flags are inferred: both are UNKNOWN/UNSUPPORTED until independently source-backed. Scope, UTC query timestamp, source kind and unauthenticated source-revision UNKNOWN are explicit. No claims of runtime memory or client agreement.

`total_rows`, `row_count`, `has_more`, `next_cursor`, `truncated` and `complete` describe only one scoped SELECT transaction. A page with offset > 0 is never marked a complete snapshot. Each HTTP call is an independent transaction: pages cannot be combined into an authoritative atomic snapshot without an independently verified revision/snapshot mechanism. Empty authorized container can be complete; absent DB connection is UNAVAILABLE. Errors remain fail-closed.

Local future acceptance (not executed): configure disposable character, loopback SELECT-only account, verify safe1/safe2 equal slots, 101+ records, source-accurate exdata, installed furnishing flags independently, client inventory timestamps, source/deployment attestation DSP #59, gardening mutation guard DSP #60, no cross-char access, read-only DB grants and no GUI/GM/client invocation. Do not promote scenario records or authorize gameplay.
