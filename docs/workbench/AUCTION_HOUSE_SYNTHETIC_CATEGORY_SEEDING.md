# Auction House synthetic category seeding

Status: DSP/Topaz Test-only category seeding implemented.

This administrative path expands one Auction House category into bounded synthetic listings. It is intended for economy seeding, testing, and backend administration on legacy servers where direct player-backed inventory transactions may be unavailable or non-transactional.

## Preview

`POST /auction-house/test-write/synthetic-category-preview.json`

Inputs:

- `category_id`
- `price`
- `stack_mode`: `single`, `stack`, or `auto`
- `copies_per_item`: 1-5
- `limit_items`: 1-250

The preview returns the exact item set, stack decisions, listing-row count, and total injected supply units. It performs no writes.

`stack` includes only stackable items and posts full stacks. `auto` posts stackable items as stacks and non-stackable items as singles.

## Execute

`POST /auction-house/test-write/synthetic-category-seed.json`

Execution additionally requires:

- `seller_id`
- exact active Test profile-name `confirmation`
- existing guarded DSP/Topaz Test write feature flag and lineage gates.

The executor expands the category again from live `item_basic` data, then invokes the established single-row synthetic listing executor for each requested copy.

## Safety and economics

- Maximum 250 distinct category items per request.
- Maximum 5 copies per item.
- Maximum 500 attempted listing rows per request.
- Each listing has its own commit/rollback boundary.
- Partial success is reported explicitly with per-item/per-copy results.
- No seller Inventory is removed.
- No Auction House listing fee is charged.
- The response reports total injected supply units.
- Live environments remain blocked by the shared Test-write gate.

Synthetic seeding deliberately does not pretend that a player posted the items. It is an administrative supply injection.

This path remains usable on historical MyISAM inventory schemas because it does not mutate player Inventory or gil.
