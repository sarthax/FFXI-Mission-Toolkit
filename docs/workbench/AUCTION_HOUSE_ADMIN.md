# Auction House Administration

## Purpose

`Server -> Auction House Administration` is an administrator-facing view of live FFXI auction-house state and economy health. The first implementation phase is deliberately **read only** so it can be validated against live DSP, Topaz, LandSandBoat, and derived server databases before any mutation workflow is introduced.

## Phase 1 surface

The read-only service provides:

- active server/environment resolution through the toolkit's existing server configuration;
- live `auction_house` and `item_basic` schema discovery instead of assuming one upstream revision;
- AH-category browsing and item search by name or item ID;
- local client/DAT item icons through the existing persistent item asset cache;
- active listings with seller, listing time, lot type, and asking price;
- completed-sale history with seller, buyer, sale time, lot type, and sale price;
- 7/30/90-day daily price/volume summaries;
- economy totals such as active listings, recent sales, transacted gil, and distinct buyers/sellers;
- explicit capability reporting for schema-dependent fields such as LandSandBoat's numeric buyer ID.

The current category UI intentionally exposes verified numeric AH category IDs when no authoritative category-name source is available. A later read-only enhancement may attach human-readable client/server category labels once they are sourced and tested.

## Safety contract

Phase 1 contains no Auction House mutation contract. `AuctionHouseService` has no create, add, insert, update, delete, buy, sell, purchase, purge, or delivery operation, and the HTTP router exposes GET routes only.

This is stronger than simply hiding write buttons: there is no Phase 1 service method that can change Auction House state.

## Server compatibility

The schema adapter inspects the live database with `DESCRIBE` and resolves logical fields from known historical aliases. Current LandSandBoat-compatible schemas are distinguishable by their numeric `buyer` field; older DSP/Topaz-compatible layouts continue to work through buyer/seller name fields. The family value is a schema-shape hint rather than a claim that a fork is a pristine upstream checkout.

## HTTP surface

- `/auction-house`
- `/auction-house/status.json`
- `/auction-house/overview.json`
- `/auction-house/categories.json`
- `/auction-house/items.json`
- `/auction-house/items/{item_id}.json`
- `/auction-house/items/{item_id}/history.json`
- `/auction-house/items/{item_id}/trends.json`
- `/auction-house/items/{item_id}/icon.png`

## Planned later phases

Write functionality remains intentionally out of scope until this read-only layer is exercised against representative server generations. Planned later work includes guarded single-item list/buy operations, dry-run bulk stocking and cleanup, auditable administrative purchases, Mog inbox distribution with saved templates, and broader economy-health/anomaly analysis. Public-facing economy views, if pursued, should consume a separate read-only presentation API rather than administrative mutation endpoints.
