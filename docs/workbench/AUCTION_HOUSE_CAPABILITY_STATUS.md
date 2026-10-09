# Auction House capability and status

This is the authoritative operator summary for the Auction House administration module.

## Current operational assessment — 2026-10-09

**Core DSP administration: feature-complete / maintenance mode.** The project owner has tested the unified Auction House UI against DSP and reports it clean and stable. This is not a claim that every recently merged Test-only executor has completed an individual local acceptance run.

**Final implementation packages merged:** non-atomic DSP MyISAM pre-write recovery journal and operator cases, per-recipient interrupted Mog delivery journal, one-time named Test-profile reward scheduling, and experimental source-checked custom augmented Mog rewards (#786); Character Editor-style augment and item selection (#787, #792); item detail icons, hover information and circular Item Browser / Editor links (#795); Buyers, Sellers, Restock and Cleanup item-search/navigation (#797); remembered safe workspace state (#802), read-only CSV exports (#808), browser-local item/seller favorites (#812), contextual Add-to-Inbox action (#814), named reusable augmented configuration catalog (#815), and shared Workbench item-picker foundation (#816).

**Operating boundaries:** scheduled reward campaigns are one-time and Test-only, with no automatic retry after uncertain execution. The augment configuration library saves definitions, not permission to deliver; custom augmented mail delivery is DSP Test-only, disabled by default, and requires a verified in-game Mog pickup/augment-persistence test before broader acceptance. The new shared item-picker is integrated into AH Restock/Cleanup/Inbox but not yet migrated across Character Editor. MyISAM interruption cases are diagnostic, not atomic rollback or automatic repair.

**Remaining acceptance/maintenance:** verify new MyISAM and Inbox interruption reporting, one-time scheduled sends, custom augmented-item pickup on disposable DSP Test; accumulate multi-day live snapshot evidence; independently validate Topaz; defer broader LSB writes until a runnable LSB Test exists. Production writes remain blocked.

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

## Reward, schedule and augment boundaries

Ordinary item/gil bundles, account-wide recipient selection, saved templates, reward history, replay protection, interrupted-recipient evidence, and a searchable Inbox item catalog are implemented. One-time scheduled campaigns are operator-approved for a named DSP/Topaz Test environment and recheck gates at execution; cancellation and review-required states never bypass the standard approval flow.

Custom item augmentation supports source-backed ID/value selection (up to four slots), named saved configurations, encoding preview, and a separate disabled-by-default, one-recipient **DSP Test-only** mail executor. No unverified extra payload is silently converted into a plain item. A real pickup test on the configured DSP server must confirm augments persist before wider delivery use.

## Navigation and exports

The unified hub includes icon-backed item selection and details, compact hover facts, two-way deep links with Item Browser and Item Editor, shared AH pickers in Restock/Cleanup/Inbox, browser-local favorites and remembered navigation/filter state, quick Add-to-Inbox action, and read-only CSV export in Items, Sellers, Restock and Cleanup. These are UI features; they do not change write authorization.

## Audit boundary

The Activity page combines execution outcomes, preview/replay evidence, and reward campaign history. Execution-event recording begins at the point the feature was introduced; older mutations are not fabricated from current server state.

## Operator UI

All Auction House tools live inside the single hub at **Server -> Auction House** (`/auction-house`); legacy page URLs forward there. The hub header chip resolves the active environment, schema family, scoped Test-write readiness, and transactional-table blockers. Use **Auction House -> More tools -> Status & help** for the in-tool version of this document.

## Economy snapshots

The game server keeps no supply history, so the toolkit records one snapshot per UTC day (active listings, asking gil, 7-day sales, sell-through, per-category and per-item supply) into its own SQLite DB (`ffxi_zone_database.db`, tables `ah_snapshot*`). An hourly background loop records it when missing; "Record now" forces it. This writes only to the toolkit DB, never the game database, and needs no write flag.
