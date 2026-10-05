# Auction House player-backed purchase

Status: guarded DSP/Topaz Test-only exact-row purchase path.

## Purpose

The Listing Manager can now attempt a real purchase of one exact active Auction House row for a selected character. This is intentionally different from normal client behavior: the admin chooses an exact auction ID, so the executor never substitutes the cheapest qualifying row.

## Safety gates

Player purchase requires all existing legacy Test-write gates plus:

- buyer character exists;
- buyer is offline;
- buyer has a verified free Inventory slot;
- buyer has a valid gil row in Inventory slot 0;
- buyer has enough gil for the exact asking price;
- buyer and seller are different characters;
- native `auction_house_buy` and `delivery_box_insert` purchase prerequisites are present;
- `auction_house`, `char_inventory`, and `delivery_box` all use transactional storage engines.

Historical Topaz/DSP schemas may use MyISAM for `char_inventory`. That engine cannot participate in a rollback-safe transaction, so the direct database executor fails closed and reports the blocking table instead of pretending the operation is atomic.

## Transactional execution

When all required tables are transactional, the executor:

1. locks the exact auction row `FOR UPDATE`;
2. requires the row to remain active and at the expected asking price;
3. locks the buyer gil row and verifies sufficient funds;
4. debits buyer gil with compare-and-swap semantics;
5. inserts the single item or full stack into the previously verified free Inventory slot;
6. marks the exact AH row sold with the buyer name and asking price;
7. requires the native seller-settlement trigger to add exactly one delivery-box gil row;
8. verifies buyer gil, buyer inventory, AH sold state, and seller settlement before commit;
9. rolls back on every mismatch or exception.

## UI

The AH Listing Manager now exposes both **Player Preview** and **Player Buy** actions. The write action still requires the exact active Test profile name as confirmation and remains unavailable on Live.

## Remaining legacy gap

For stock MyISAM-based DSP/Topaz databases, a true rollback-safe player purchase cannot be implemented as one direct SQL transaction. The remaining options are either:

- a server-native admin command/API that reuses the map server's inventory/AH code, or
- an explicitly non-atomic compensated operation with crash-recovery journaling.

The first option is preferable for eventual production-grade legacy support.
