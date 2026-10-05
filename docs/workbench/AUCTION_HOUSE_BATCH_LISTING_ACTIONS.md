# Auction House batch listing actions

Status: guarded DSP/Topaz Test-only multi-select administration.

The Listing Manager supports selecting visible active listings and applying either **Admin Buy selected** or **Return selected**.

## Execution model

Batch operations do not create a new bulk mutation contract. Each selected listing is passed through the established single-row executor and receives its own commit/rollback boundary. A batch may therefore finish with `completed`, `partial`, or `failed` status, and the response records the result for every auction ID.

This is intentional: a failure on one stale/full/unavailable listing must not make the toolkit claim that already committed listings were rolled back.

Batches are limited to 100 unique auction IDs and retain the DSP/Topaz Test environment, feature flag, and exact profile-name confirmation gates.

## Return strategy

Return now chooses the safest verified storage path:

1. if `auction_house` and `char_inventory` are transactional, use the native-style direct Inventory return;
2. if legacy Inventory is non-transactional but `auction_house` and `delivery_box` are transactional, remove the listing and queue the single/full-stack item to the seller delivery box using the verified legacy delivery schema and `delivery_box_insert` trigger;
3. if neither rollback-safe strategy is available, fail closed without removing the listing.

The original Auction House listing fee is not refunded.

## Current batch actions

- `admin_buy` — consumes the item administratively and pays the seller through the native AH settlement trigger path.
- `return_to_seller` — restores the item to Inventory or delivery box according to the safe strategy above.

Player-backed purchases remain single-row actions because buyer gil and inventory capacity must be validated for each exact purchase.
