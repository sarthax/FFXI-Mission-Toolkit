# Auction House capability and status

This is the authoritative operator summary for the Auction House administration module.

## Capability model

The module is deliberately split between broad read-only administration and narrowly scoped DSP/Topaz Test-environment executors. A scoped Test executor being available does **not** mean Auction House writes are globally enabled.

### Read-only surfaces

- Auction House overview, browse, item history, trends and health
- Listing browser
- Economy intelligence (trends, queues, supply snapshots, baselines, admin-impact overlay)
- Reward campaign history
- Unified Activity/Audit timeline
- Preview and validation endpoints

### Scoped DSP/Topaz Test writes

These remain behind the existing Auction House Test-write feature flag, named Test environment classification, compatible discovered schema, and exact active-profile confirmation:

- price change
- synthetic listing
- Admin Buy
- Return to seller
- batch Admin Buy / Return
- rule-driven cleanup
- synthetic category seeding
- market history/scenario seeding and clear (Seeder tab; fake sellers 990000-990024 only)
- player-backed listing when the required tables are transactional
- player purchase when the required tables are transactional
- reward/Mog delivery

Preview-bound operations re-read live state before mutation. Replay-protected flows require a fresh replay ID and reject duplicate use.

## Legacy MyISAM boundary

Historical DSP/Topaz layouts can use MyISAM for character Inventory. Because MyISAM cannot provide transactional rollback, operations that require atomic Inventory/gil changes fail closed when the relevant tables are non-transactional. The toolkit must not claim rollback safety that the database engine cannot provide.

Return-to-seller can fall back to the verified Mog delivery path where direct Inventory return is not rollback-safe.

## LSB

LSB schemas/source remain useful reference evidence, but current runnable write validation is intentionally focused on DSP and Topaz Test environments. LSB execution should remain deferred until a runnable LSB Test environment exists.

## Live environments

Live writes remain blocked. Scoped Test execution never enables unrestricted or Live mutation.

## Reward limitations

Reward bundles support ordinary item delivery. Augmented/custom `extra` payload generation remains intentionally unsupported until DSP/Topaz item-extra serialization is proven.

## Audit boundary

The Activity page combines execution outcomes, preview/replay evidence, and reward campaign history. Execution-event recording begins at the point the feature was introduced; older mutations are not fabricated from current server state.

## Operator UI

All Auction House tools live inside the single hub at **Server -> Auction House** (`/auction-house`); legacy page URLs forward there. The hub header chip resolves the active environment, schema family, scoped Test-write readiness, and transactional-table blockers. Use **Auction House -> More tools -> Status & help** for the in-tool version of this document.

## Economy snapshots

The game server keeps no supply history, so the toolkit records one snapshot per UTC day (active listings, asking gil, 7-day sales, sell-through, per-category and per-item supply) into its own SQLite DB (`ffxi_zone_database.db`, tables `ah_snapshot*`). An hourly background loop records it when missing; "Record now" forces it. This writes only to the toolkit DB, never the game database, and needs no write flag.
