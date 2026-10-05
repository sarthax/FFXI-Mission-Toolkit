# Auction House TEST executor

Status: **first real write primitive; LSB Test only**

The Auction House module now has a deliberately narrow database-backed executor used to prove the guarded write path before player listing or purchase execution is enabled.

## Safety boundary

Execution is allowed only when all of the following are true:

- the active named environment is enabled and active;
- `environment == test`;
- `family == lsb`;
- the discovered live schema is `lsb-compatible`;
- `FFXI_MISSION_TOOLKIT_AH_TEST_WRITES=1` is set;
- the administrator supplies the active Test profile name exactly as confirmation.

LIVE, DSP, Topaz, custom, legacy, inactive, disabled, and schema-mismatched environments fail closed. There is no free-form SQL endpoint.

## First write operation: active listing price change

`execute_lsb_test_price_change()` changes only the asking price of one already-active Auction House row. This operation was chosen because it proves the server write transaction without pretending to reproduce LandSandBoat's `ItemClaimTransaction` inventory/gil semantics.

The transaction:

1. starts one database transaction;
2. locks the exact auction row with `SELECT ... FOR UPDATE`;
3. verifies the row is still active;
4. verifies the current price exactly matches the expected/previewed price;
5. updates with a compare-and-swap predicate that includes auction ID, expected price, and active-sale state;
6. requires exactly one affected row;
7. re-reads and verifies the post-state while still locked;
8. commits only after verification;
9. rolls back on every exception or mismatch.

## Why listing/purchase are still blocked

LandSandBoat player listing and purchase paths involve more than the `auction_house` row. The upstream source uses `ItemClaimTransaction` to coordinate inventory and gil, while Auction House triggers participate in seller settlement/delivery-box behavior. The toolkit must not replace that with a partial direct-SQL imitation.

The next executor milestones are therefore:

1. expose the TEST executor gate/readiness in the admin surface;
2. persist executor outcome events in the local append-only AH audit ledger;
3. validate the price-change primitive against a real configured LSB Test database;
4. build a source-faithful LSB admin listing operation with explicit inventory/gil semantics or a deliberately synthetic admin-listing contract;
5. build normal purchase only after two-buyer concurrency and rollback behavior are proven;
6. keep DSP/Topaz and LIVE execution disabled until independently validated.
