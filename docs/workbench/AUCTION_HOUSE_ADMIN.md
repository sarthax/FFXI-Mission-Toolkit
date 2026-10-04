# Auction House Administration

## Purpose

`Server -> Auction House Administration` is an administrator-facing view of live FFXI auction-house state and economy health. Phase 1 established a read-only cross-lineage data layer. Phase 2 begins with **preview-only** administrative action contracts so write semantics can be validated before any mutation endpoint exists.

## Read and analysis surface

The service provides:

- active server/environment resolution through the toolkit's existing server configuration;
- live `auction_house` and `item_basic` schema discovery instead of assuming one upstream revision;
- canonical FFXI AH-category browsing (Weapons, Armor, Scrolls, Materials, Food, and related client submenus) while preserving numeric category IDs and unknown custom-fork values;
- item search by name or item ID;
- local client/DAT item icons through the existing persistent item asset cache;
- active listings with seller, listing time, lot type, and asking price;
- completed-sale history with seller, buyer, sale time, lot type, and sale price;
- 7/30/90-day daily price/volume summaries separated by single-item and stack lots;
- economy totals such as active listings, recent sales, transacted gil, and distinct buyers/sellers;
- explicit capability reporting for schema-dependent fields such as LandSandBoat's numeric buyer ID.

The canonical category labels follow the server/client AH category values used by LandSandBoat and retained by the DSP/Topaz lineage. The live `item_basic` category value remains authoritative. Unknown values from custom forks are surfaced as `Custom / Unknown` instead of being rejected or mislabelled.

## Phase 2 preview-only administration

Two administrative workflows now have deterministic previews:

### Preview listing

Inputs:

- item ID;
- seller character ID;
- asking price;
- single-item or full-stack lot.

The preview validates the item, its AH category, stackability, and the seller identity from the active server database. It reports quantity and price-per-item and records the exact item/seller snapshot used for the preview.

### Preview purchase / cleanup

Inputs:

- active auction ID;
- `admin_cleanup` or `normal_purchase` mode;
- buyer character ID for a normal purchase.

The preview snapshots the exact unsold auction. `admin_cleanup` explicitly reports seller compensation and the resulting administrative gil injection. `normal_purchase` reports both buyer charge and seller compensation and requires a valid buyer snapshot.

These previews are intended to become the stale-state boundary for later apply endpoints: an apply operation must re-read and match the previewed row before mutation.

## Safety contract

There is still **no Auction House mutation contract**.

`AuctionHouseService` exposes SELECT-only read/snapshot methods and has no create, add, insert, update, delete, buy, sell, purchase, purge, or delivery method. The only POST routes are explicitly named `/preview.json`; there is no `/apply`, `/commit`, `/delete`, or equivalent mutation route.

Every preview includes a blocking `preview_only` warning and `apply_supported: false`. The GUI labels the controls **PREVIEW ONLY / NO WRITES**.

## Server compatibility

The schema adapter inspects the live database with `DESCRIBE` and resolves logical fields from known historical aliases. Current LandSandBoat-compatible schemas are distinguishable by their numeric `buyer` field; older DSP/Topaz-compatible layouts continue to work through buyer/seller name fields. The family value is a schema-shape hint rather than a claim that a fork is a pristine upstream checkout.

Character identity lookup for previews also discovers the common `chars` ID/name aliases rather than assuming only one lineage spelling.

## HTTP surface

Read endpoints:

- `/auction-house`
- `/auction-house/status.json`
- `/auction-house/overview.json`
- `/auction-house/categories.json`
- `/auction-house/items.json`
- `/auction-house/items/{item_id}.json`
- `/auction-house/items/{item_id}/history.json`
- `/auction-house/items/{item_id}/trends.json`
- `/auction-house/items/{item_id}/icon.png`

Preview-only POST endpoints:

- `/auction-house/admin/list/preview.json`
- `/auction-house/admin/purchase/preview.json`

## Planned next phases

The next guarded slice is to define actual lineage-specific write adapters and verification fixtures without exposing them immediately through the GUI. Before an apply route is enabled it should require a fresh preview snapshot, explicit active-environment confirmation, transaction boundaries, stale-state rejection, and an audit record. After single-item writes are proven, later work can add dry-run bulk stocking and stale-auction cleanup, Mog inbox distribution with saved templates, and broader economy-health/anomaly analysis. Public-facing economy views, if pursued, should consume a separate read-only presentation API rather than administrative mutation endpoints.
