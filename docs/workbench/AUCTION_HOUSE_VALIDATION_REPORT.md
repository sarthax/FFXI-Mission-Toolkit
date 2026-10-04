# Auction House unified preview validation

Auction House administration uses one read-only validation surface with lineage-specific backends for LSB and for legacy DSP/Topaz servers.

## Ordered validation stages

1. Active named server environment and explicit lineage.
2. Source-backed lineage/schema agreement.
3. Live Auction House table/trigger prerequisites.
4. Fresh database reread and stale-preview checks.
5. Lineage-specific policy gate.
6. Preview policy binding/drift validation.
7. Listing or purchase invariants.

The orchestrator returns each stage separately plus a flattened blocker list so an administrator can see exactly why a preview is blocked.

## Lineage separation

DSP/Topaz validation loads the active legacy Auction House fee/tax/listing-limit configuration and binds the preview to that configuration fingerprint.

LSB uses its own source-backed settings model from `settings/default/map.lua`; it does not reuse the DSP/Topaz `.conf` parser. The LSB validator reads and fingerprints:

- `AH_BASE_FEE_SINGLE`
- `AH_BASE_FEE_STACKS`
- `AH_TAX_RATE_SINGLE`
- `AH_TAX_RATE_STACKS`
- `AH_MAX_FEE`
- `AH_LIST_LIMIT`

Missing or malformed LSB settings fail closed rather than falling back to toolkit defaults.

LSB previews are now bound at preview creation time to the active settings source path, source kind, lineage family, and SHA-256 policy fingerprint. Validation reloads the active LSB policy and blocks the preview if that binding is missing, points at a different policy source, identifies a different lineage/source kind, or has a different fingerprint. This prevents a preview generated under one AH fee/listing policy from later being treated as current after server settings change.

The LSB path also validates:

- explicit `lsb` environment identity,
- `lsb-compatible` schema agreement,
- `auction_house_list`, `auction_house_buy`, and `delivery_box_insert` readiness as appropriate to the operation,
- fresh read-only item/seller or listing/buyer snapshots,
- preview environment/fingerprint freshness,
- seller inventory quantity for singles/full stacks,
- source-matched listing fee and seller gil sufficiency,
- active listing limit,
- buyer gil sufficiency,
- buyer inventory free-slot readiness,
- cheapest qualifying active listing stability,
- seller delivery-box settlement readability.

These checks mirror the source-observable prerequisites in LandSandBoat `auctionutils.cpp`; they do not execute those operations.

Every lineage-specific reread starts `START TRANSACTION READ ONLY` and rolls back unconditionally.

## Status model

`read_only_validation_ready` means all live evidence gates for the selected lineage are healthy. It does **not** authorize a write.

`execution_ready`, `executor_enabled`, and `write_enabled` remain `false` in this phase for every lineage.

DSP/Topaz retain `lineage_execution_contract_incomplete` as an execution blocker even when their complete read-only evidence chain is healthy. LSB source semantics are verified, but the stronger LSB validation path still does not introduce an executor or mutation route.

## Fail-closed behavior

Validation is blocked for stale database state, wrong/missing environment binding, lineage/schema mismatch, missing required tables/triggers, unresolved policy/settings, missing or drifted policy binding, insufficient inventory or gil, listing-limit exhaustion, buyer inventory capacity problems, cheapest-listing drift, unverifiable seller settlement state, or unsupported lineage.

## Safety

The report performs no Auction House mutation and contains no commit/apply path. The presentation endpoint remains a `/preview.json` POST and only composes read-only probes and validation evidence.
