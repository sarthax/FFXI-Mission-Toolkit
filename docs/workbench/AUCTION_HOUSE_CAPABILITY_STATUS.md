# Auction House capability and status

This is the authoritative operator summary for the Auction House administration module.

## Capability model

The module is deliberately split between broad read-only administration and narrowly scoped DSP/Topaz Test-environment executors. A scoped Test executor being available does **not** mean Auction House writes are globally enabled.

### Read-only surfaces

- Auction House overview, browse, item history, trends and health
- Listing browser
- Economy intelligence
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

Every major Auction House page uses the shared AH sub-navigation and capability banner. The banner resolves the active environment, schema family, scoped Test-write readiness, and transactional-table blockers. Use **Server -> AH Help / Status** for the in-tool version of this document.
