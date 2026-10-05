# Auction House legacy Test executor

Status: guarded write-capable slice for DSP/Topaz test environments.

The legacy executor now supports two intentionally narrow administration operations:

1. change the asking price on one already-active Auction House listing;
2. create one synthetic admin listing for a real item/seller pair.

These operations prove database write safety without yet reproducing DSP/Topaz player inventory, listing-fee, buyer-gil, or delivery-box transaction semantics.

## Guardrails

Execution is permitted only when all of the following are true:

- active named environment identifies `dsp` or `topaz`;
- environment class is `test`;
- live schema shape is `legacy-dsp-topaz-compatible`;
- `FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES=1`;
- administrator supplies the exact active profile name as confirmation.

Live, LSB, custom, auto, legacy/unclassified, disabled, and inactive environments fail closed.

## Price-change contract

1. begin one database transaction;
2. select the exact Auction House row `FOR UPDATE`;
3. require the row to remain active/unsold;
4. require its current asking price to equal the expected old price;
5. update exactly that row using auction ID + old price + unsold state as the compare-and-swap predicate;
6. require exactly one affected row;
7. reread the row and verify the new asking price while still active;
8. commit only after post-state verification;
9. rollback on every mismatch or exception.

## Synthetic admin listing contract

The synthetic listing operation is deliberately **not** represented as a normal player listing.

It:

- validates that the item exists and belongs to an Auction House category;
- validates stackability when a stack is requested;
- validates that the selected seller character exists;
- inserts exactly one active `auction_house` row using runtime-discovered DSP/Topaz columns;
- verifies the inserted item, stack flag, seller, asking price, sale value, and sold timestamp before commit;
- rolls back on any mismatch.

It does **not** remove seller inventory or charge a listing fee. The response reports those facts and the injected quantity explicitly. If the synthetic listing later sells, normal legacy `auction_house_buy` / `delivery_box_insert` trigger behavior still controls seller settlement.

Column names come from runtime schema discovery. No free-form SQL input is exposed.

## API surface

Write-capable endpoints are isolated under:

`/auction-house/test-write/...`

Current endpoints:

- `POST /auction-house/test-write/readiness.json`
- `POST /auction-house/test-write/price-change.json`
- `POST /auction-house/test-write/synthetic-listing.json`

The readiness endpoint performs no mutation.

## Remaining legacy write milestones

1. bind executor outcome records into the append-only Auction House audit ledger;
2. validate price change and synthetic listing against configured DSP and Topaz Test databases;
3. implement a true player-backed listing transaction using an exact inventory slot/quantity, active config fee, seller gil debit, and listing row in one transaction;
4. prove rollback of player listing row, inventory, and gil together;
5. implement purchase with atomic cheapest-row claim, buyer debit/item grant, and seller delivery settlement verification;
6. add two-connection concurrency tests before bulk operations;
7. build mass add/buy only on top of the proven single-operation executor paths.
