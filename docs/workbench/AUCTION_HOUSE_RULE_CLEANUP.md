# Auction House rule-driven cleanup

Status: DSP/Topaz Test-only administrative cleanup built on the existing single-row Admin Buy and safe Return executors.

## Purpose

The cleanup surface lets an administrator select stale or targeted active listings by rule, inspect the exact rows, then act on only that previewed set. It is intended for economy maintenance such as returning old listings, clearing one seller's inventory, or administratively buying a bounded category/price slice.

## Filters

The preview supports seller ID/name, category ID, item ID, minimum/maximum asking price, listed-before timestamp, and minimum age in days. Results are capped at 100 listings because the existing batch executor is bounded to 100 rows.

Age filters are resolved to an explicit `listed_before` epoch timestamp at preview time. The UI includes 30-day and 90-day stale presets, but they use the same underlying criteria model.

## Preview binding

Preview is read-only. It returns the exact active auction IDs plus asking price, seller, item, and listed timestamp, aggregate asking value, age summary, and a SHA-256 preview token.

The token covers the normalized criteria and exact target identity/state. Before execution the toolkit reruns the live selector and recomputes the token. Any added/removed listing, asking-price change, item/seller change, or listed timestamp difference causes execution to fail closed as a stale preview.

## Execution

Supported actions are:

- `admin_buy`: uses the established single-row administrative sale executor and native seller settlement path.
- `return_to_seller`: uses the established safe Return selector, preferring rollback-safe Inventory return and falling back to delivery-box return where required.

Each listing retains its own transaction boundary. Partial success is therefore possible and is reported explicitly; a later failure does not imply that earlier committed rows were rolled back.

The existing DSP/Topaz Test gate remains mandatory: active named Test environment, supported lineage/schema, write feature flag, and exact Test profile-name confirmation. Live, LSB, custom, and unclassified environments remain blocked.

## Routes

- `GET /auction-house/cleanup`
- `POST /auction-house/cleanup/preview.json`
- `POST /auction-house/test-write/cleanup.json`

The page is exposed as **Server → AH Cleanup**.
