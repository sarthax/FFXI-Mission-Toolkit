# Auction House unified preview validation

Auction House administration uses one read-only validation surface with lineage-specific backends for LSB and for legacy DSP/Topaz servers.

## Ordered validation stages

1. Active named server environment and explicit lineage.
2. Source-backed lineage/schema agreement.
3. Live Auction House table/trigger prerequisites.
4. Fresh database reread and stale-preview checks.
5. Lineage-specific policy gate.
6. Lineage-specific policy binding.
7. Listing or purchase invariants.

The orchestrator returns each stage separately plus a flattened blocker list so an administrator can see exactly why a preview is blocked.

## Lineage separation

DSP/Topaz validation loads the active legacy Auction House fee/tax/listing-limit configuration and binds the preview to that configuration fingerprint.

LSB validation deliberately does **not** import those legacy configuration assumptions. Its policy and policy-binding stages report the DSP/Topaz external fee-policy model as not applicable, while the LSB path validates:

- explicit `lsb` environment identity,
- `lsb-compatible` schema agreement,
- `auction_house_list`, `auction_house_buy`, and `delivery_box_insert` readiness as appropriate to the operation,
- a fresh read-only reread of item/seller or listing/buyer state,
- preview environment/fingerprint freshness,
- basic live listing, seller, item, and buyer invariants.

Every lineage-specific reread starts `START TRANSACTION READ ONLY` and rolls back unconditionally.

## Status model

`read_only_validation_ready` means all live evidence gates for the selected lineage are healthy. It does **not** authorize a write.

`execution_ready`, `executor_enabled`, and `write_enabled` remain `false` in this phase for every lineage.

DSP/Topaz retain `lineage_execution_contract_incomplete` as an execution blocker even when their complete read-only evidence chain is healthy. LSB source semantics are verified, but this validation parity work still does not introduce an executor or mutation route.

## Fail-closed behavior

Validation is blocked for stale database state, wrong/missing environment binding, lineage/schema mismatch, missing required tables/triggers, missing live item/seller/listing/buyer state, legacy policy drift where applicable, or any unsupported lineage.

## Safety

The report performs no Auction House mutation and contains no commit/apply path. The presentation endpoint remains a `/preview.json` POST and only composes read-only probes and validation evidence.
