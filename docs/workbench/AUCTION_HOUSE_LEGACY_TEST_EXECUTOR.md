# Auction House legacy Test executor

Status: first guarded write-capable slice for DSP/Topaz test environments.

This executor intentionally starts with changing the asking price on one already-active Auction House listing. That operation proves database write safety without reproducing DSP/Topaz player inventory, listing-fee, buyer-gil, or delivery-box semantics.

## Guardrails

Execution is permitted only when all of the following are true:

- active named environment identifies `dsp` or `topaz`;
- environment class is `test`;
- live schema shape is `legacy-dsp-topaz-compatible`;
- `FFXI_MISSION_TOOLKIT_AH_LEGACY_TEST_WRITES=1`;
- administrator supplies the exact active profile name as confirmation;
- auction ID, expected old price, and new price are explicit positive integers.

Live, LSB, custom, auto, legacy/unclassified, disabled, and inactive environments fail closed.

## Transaction contract

Price change:

1. begin one database transaction;
2. select the exact Auction House row `FOR UPDATE`;
3. require the row to remain active/unsold;
4. require its current asking price to equal the expected old price;
5. update exactly that row using auction ID + old price + unsold state as the compare-and-swap predicate;
6. require exactly one affected row;
7. reread the row and verify the new asking price while still active;
8. commit only after post-state verification;
9. rollback on every mismatch or exception.

Column names come from runtime schema discovery. No free-form SQL input is exposed.

## Why price change first

DSP/Topaz player listing and purchase are application-managed operations. Listing coordinates Auction House insertion, inventory removal, listing fee debit, and stack semantics. Purchase coordinates cheapest-row claim, buyer inventory/gil, and the `auction_house_buy` / `delivery_box_insert` settlement triggers. Those flows remain separate executor milestones.

## Next legacy write milestones

1. expose executor readiness and price change through Auction House admin API/UI;
2. bind executor outcome records into the append-only Auction House audit ledger;
3. validate price change against configured DSP and Topaz Test databases;
4. implement listing transaction with exact inventory slot/quantity + fee semantics;
5. prove rollback of listing row, inventory, and gil together;
6. implement purchase with atomic cheapest-row claim, buyer debit/item grant, and seller delivery settlement verification;
7. add two-connection concurrency tests before bulk operations.
