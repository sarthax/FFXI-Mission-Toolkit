# Auction House Listing Manager

Status: DSP/Topaz granular administration foundation.

## Purpose

The Listing Manager provides row-level control over active Auction House listings rather than only item-level market views.

Admins can browse/filter active listings by:

- seller character ID;
- seller name;
- Auction House category;
- item ID;
- item name;
- auction row ID.

Each result preserves the exact auction ID, item, seller, stack/single lot type, quantity, listing timestamp, and asking price.

## Row actions

### Admin Buy

DSP/Topaz Test-only guarded operation.

Admin Buy closes the exact active row as an administrative sale. It does not add the item to a buyer inventory and does not charge buyer gil. The seller is compensated through the native legacy `auction_house_buy` -> `delivery_box_insert` trigger path.

Safety requirements:

- active DSP or Topaz Test environment;
- legacy-compatible Auction House schema;
- explicit Test-write feature flag;
- exact active Test profile-name confirmation;
- expected asking price must still match;
- `auction_house_buy` and `delivery_box_insert` prerequisites must be present;
- exactly one row must be claimed;
- seller settlement must appear exactly once before commit.

If seller settlement cannot be observed, the transaction rolls back.

### Return to Seller

DSP/Topaz Test-only guarded operation modeled on the native legacy Auction House cancel path.

The operation:

1. locks the exact active Auction House row;
2. verifies it remains unsold;
3. verifies the seller and item;
4. requires the seller to be offline;
5. requires a verified free Inventory slot;
6. deletes exactly the active Auction House row;
7. restores one item or one full stack to seller Inventory;
8. verifies both the restored inventory row and removed Auction House row;
9. commits only after both sides are correct.

If Inventory is full, seller state is unknown/online, or any verification fails, the transaction rolls back and the listing remains.

Native DSP/Topaz cancellation returns the item but does not refund the original Auction House listing fee. The toolkit preserves that behavior.

### Player Buy Preview

The manager exposes the existing player-purchase preview for an exact listing and buyer character ID. Player-backed execution remains a separate milestone because it must coordinate buyer gil, inventory delivery, cheapest-row claim semantics, and seller settlement atomically.

## UI

`/auction-house/listing-manager`

The page is also contributed to the Server workspace as `AH Listing Manager`.

## API

Read-only browser:

- `GET /auction-house/listings.json`

Guarded DSP/Topaz Test actions:

- `POST /auction-house/test-write/admin-buy.json`
- `POST /auction-house/test-write/return-to-seller.json`

Player-backed preview remains:

- `POST /auction-house/admin/purchase/preview.json`

## Next milestones

1. append executor outcomes to the Auction House audit ledger;
2. add player-backed purchase execution;
3. add true player-backed listing execution;
4. add multi-select/batch return and admin-buy using the same single-row executor contracts;
5. add seller-centric summary views and aging/stale thresholds;
6. add pagination for very large Auction Houses.
