# Auction House Legacy DSP / Topaz Lineage Evidence

## Purpose

This note records the source-level evidence used by the Mission Toolkit Auction House administration module when identifying historical Darkstar Project (DSP) and Topaz database behavior.

This evidence is diagnostic only. It does **not** enable Auction House writes.

## Shared legacy listing behavior

The final public Darkstar and Topaz lineages both handle player listing in the map-server Auction House packet handler rather than with an `auction_house_list` database trigger.

The handler:

1. validates the inventory item and auctionability;
2. calculates and validates the Auction House listing fee;
3. checks the player's active-listing limit;
4. inserts the row into `auction_house` with item, stack, seller, timestamp, and price;
5. removes the listed quantity from player inventory;
6. deducts the Auction House fee from player gil.

Their `triggers.sql` files therefore do not define `auction_house_list`.

## Shared legacy purchase behavior

The legacy packet handler purchases by updating the cheapest qualifying active `auction_house` row with the buyer name, sale price, and sale timestamp. If the update succeeds, the map server adds the item to buyer inventory and debits the buyer's gil.

Both lineages define an `auction_house_buy` trigger. When an active seller row receives a non-zero sale value, that trigger inserts the seller's proceeds into `delivery_box`. Both also define `delivery_box_insert` to assign delivery-box slots.

## Toolkit interpretation

The live readiness probe may therefore report two legacy observations without claiming write readiness:

- `legacy_listing_shape_present`: the expected Auction House/item/character tables exist and `auction_house_list` is absent, which matches the application-managed listing shape;
- `legacy_purchase_prerequisites_present`: the expected Auction House/character/delivery tables and `auction_house_buy` + `delivery_box_insert` triggers exist.

These observations are intentionally weaker than an executable contract. A database with the same shape could still be a fork with changed application semantics.

## Remaining gate

DSP/Topaz remain preview-only until the toolkit has lineage-specific transaction contracts and regression fixtures that preserve:

- inventory removal and stack semantics for listing;
- listing fee calculation and debit behavior;
- seller delivery-box proceeds;
- buyer inventory delivery and gil debit;
- cheapest-qualifying-row selection and concurrency behavior;
- cancellation and rollback behavior;
- stale-preview protection and administrator audit logging.

The executor remains disabled regardless of readiness-probe output.