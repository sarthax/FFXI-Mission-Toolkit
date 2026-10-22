# R7 merged observation closeout and next bounded readback (2026-10-22)

**Scope:** design and future operator acceptance only; no DSP/client/GM/packet/database execution. Parent #1197. Existing #1296 remains open. Inventory #1310 and progression #1311 have merged; these are the current implementation, not implementation proposals.

## Source-backed merged contract

- `GET /api/supervisor/test-character-inventory-v2`: approved test charid, explicit locations 0 inventory / 1 Mog Safe / 10 Mog Safe 2, slot/itemId/quantity, opaque base64 extra. 100 rows per page; per-row extra <=4096 raw bytes and aggregate base64 <=65536 characters. Pagination, total count, has_more, INCOMPLETE and error states are explicit. Independently read pages **do not** establish an atomic inventory snapshot. Stored furnishings are not proven installed, and augment metadata is not decoded.
- `GET /api/supervisor/test-character-progression`: 1–50 unique regex-bounded named `char_vars` with found/PRESENT/ABSENT and zero distinct from missing; persisted `chars.keyitems` owned/seen bitmaps with 896 expected bytes. Character-existence check applies even if `include_keyitems=false`. Null/short KI data is incomplete, not evidence of absence.
- Both routes use the existing bearer gateway, approved disposable-character charid allowlist, parameterized SELECT-only SQL on loopback MySQL, transaction read-only declaration and UTC observation timestamps. No client-memory assertion or trusted deployed-source SHA. Full progression `complete=false` because jobs, quest status and currencies remain `UNSUPPORTED`.
- Existing evidence classifications must keep `UNAVAILABLE` (unconfigured/no grant), `UNKNOWN_CHARACTER`, `INCOMPLETE` (truncated/partial/count drift), `ABSENT` (a named var not persisted) and `UNKNOWN` (client comparison/source revision not demonstrated) distinct. Do not import into an authoritative runnable scenario catalog based only on these DB readbacks.

## Future local DSP/client acceptance checklist (not assigned/executed)

1. Record operator approval, disposable character ID, strict token configuration and HTTP listener bound to loopback. Verify denied missing/incorrect bearer and disallowed character before DB access, without collecting secrets in evidence.
2. Record DSP deployed commit, schema migration revision and independently verified running-server source fingerprint under DSP #59; do **not** infer deployment from GitHub branch.
3. Record effective SELECT-only privileges: inventory needs `chars` and `char_inventory`; progression needs `chars` and `char_vars`. Confirm denied INSERT/UPDATE/DELETE and all unrelated-table reads; no privilege expansion by this Toolkit design.
4. Validate existing/absent character, empty container, inventory versus Safe/Safe2 with colliding slot IDs, quantity, NULL/empty/zero-byte extra, 101+ records and offset paging with changing data. Verify response-cap INCOMPLETE and atomic snapshot limitation.
5. Independently record client-observed container items and timestamps; compare only matching character/container, known revision, quiescent timing and complete source scopes. Disagreement is NOT_COMPARABLE/UNKNOWN until separately investigated, not evidence of mutation or corruption.
6. Verify persisted zero versus absent named variable, 896-byte KI owned/seen length and mapping against an independently captured client bitmap. Short/NULL bitmap is INCOMPLETE. A KI does not independently prove quest completion or job unlock.
7. Check restart/save boundaries and staleness, audit provenance and missing/unknown state reporting. No GM commands, gameplay modifications, garden debug or packet injection. DSP #60 remains a separate mutation-safety concern.

## Readback prioritization (next implementation slice)

| Rank | Existing issue | Opportunity | Source certainty / dependency | Recommended disposition |
| --- | --- | --- | --- | --- |
| 1 | #1296 | Persisted main/support job and levels only | `darkstar-to-valhalla/sql/char_stats.sql` explicitly defines `charid,mjob,sjob,mlvl,slvl`; no local runtime attestation or SELECT grant yet | **Next narrow Toolkit milestone** |
| 2 | #1296 | Fixed allowlisted persisted currency subset | `sql/char_points.sql` exposes named fields but granularity, deployed revisions and supported currency mapping unverified | Later independent slice, after schema/semantics |
| 3 | #1300 | Temporary item observation | Existing XIHeadless client-seen container(3) helps; server runtime authority/status effects remain missing | Contract and synthetic evidence before implementation |
| 4 | #1298 | Entity/claim correlation | Client-observed nearby entities insufficient for live map-server identity or claim authority | DSP observer dependency |
| 5 | #1297 | Instance lifecycle/door state | Requires new map-server memory observer, instance/door revision semantics | DSP observer dependency |
| 6 | #1299 | Pyxis reward slots/claim | Requires runtime Pyxis state, token and exact player scope; highest authority/privacy complexity | DSP observer dependency |

Rank reflects feasibility, narrow read-only schema evidence, ability to test with GitHub synthetic fixtures, reuse of existing authorization, and implementation risk—not a numeric estimate of unverified scenario unlocks. #1296 references RG/MQ/VOID scenarios, but no count of newly executable scenarios is claimed.

## #1296 follow-on proposal — persisted selected job observation, P0

**Scope:** add a separate opt-in fixed-query selected-job readback to the existing supervisor progression family, or an explicitly requested field, without broadening the default output. Read `char_stats.charid,mjob,sjob,mlvl,slvl` for one approved charid **only after** reviewing DSP current source access patterns, installed schema revisions and operator-approved SELECT grant. Return only those four numeric persisted fields, timestamp, source kind, bounded field count, row/existence status, `schema_rev=UNKNOWN` and `client_agreement=UNKNOWN`. Do not decode unlocked job bits or claim quest completion. Do not silently translate nonzero IDs into names without source-verified enumeration. If a schema is not proven compatible, fail closed as UNSUPPORTED/UNAVAILABLE rather than guessing.

**Acceptance:** fixed literal parameterized SELECT, existing bearer and charid allowlist, loopback connection, read-only transaction; exact charid row or explicit missing/unknown; no cross-character results; zero vs absent; unsigned job IDs/levels validation from source rather than fabricated rules; no mutation privileges; missing SELECT grant/column/schema = sanitized UNAVAILABLE; no runtime authority inferred; `complete=false` for full progression contract. Unit synthetics cover missing/bad bearer, disallowed character, missing row, missing grant, wrong schema, NULL/zero/invalid data, partial response, duplicate rows, connection rollback/closure and deployed SHA UNKNOWN. Workflow must execute tests on exact head with Workbench and Src Layout checks.

**Required before live acceptance:** DSP #59 deployed-source attestation, exact `char_stats` schema, effective SELECT grant and independent client-visible job/level sample. Continue #1296; do not create duplicate issue or assign local agent.
