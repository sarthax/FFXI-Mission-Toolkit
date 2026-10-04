# Auction House invariant validation

This layer consumes the fresh DSP/Topaz database reread evidence and evaluates mutation preconditions without performing any mutation.

## Listing invariants

The validator checks:

- item still exists and remains Auction House eligible;
- stack listings require a stackable item and one full-stack inventory row;
- single listings require at least one matching inventory item;
- listing fee follows the verified legacy formula:
  - single: `base_fee_single + price * tax_rate_single / 100`;
  - stack: `base_fee_stacks + price * tax_rate_stacks / 100`;
  - result is truncated like the legacy integer cast and clamped to `max_fee`;
- seller gil is sufficient for the calculated listing fee;
- active listing count remains below the configured server listing limit.

The default policy object mirrors the historical Topaz retail-like configuration, but a future executor must load the active server's real map configuration. Customized server settings must not be replaced by toolkit defaults.

## Purchase and cleanup invariants

For normal purchases the validator requires enough buyer gil for the fresh asking price. Admin cleanup does not require buyer funds because no buyer is involved.

Seller proceeds remain tied to the verified `auction_house_buy` and `delivery_box_insert` path. The legacy delivery trigger does not implement a simple eight-row hard stop: visible inbox slots and queued rows use slot values beginning at 8 and can advance above that. The validator therefore checks queue integrity and can apply an optional administrative queue-slot safety ceiling instead of inventing a fixed capacity rule.

## Combined read-only pipeline

`prepare_validate_from_database_reread()` returns:

1. `PreparedTransaction` — lineage/environment, stale-preview, claim-cardinality, and cheapest-row checks;
2. `RereadEvidence` — the fresh read-only database evidence;
3. `InvariantReport` — fee, inventory, listing-limit, funds, and settlement readiness.

These remain separate so a caller can distinguish a stale preview from a current-but-invalid transaction state.

## Safety boundary

This layer has no SQL mutation primitive, no commit path, no Apply/Commit endpoint, and always reports `executable = false` / `executor_enabled = false` where execution state is represented.

## Remaining gates

Before any write executor can be considered:

1. ingest the actual active DSP/Topaz Auction House configuration instead of relying on policy defaults;
2. pin the exact inventory row/slot selected for listing so execution cannot choose a different matching row;
3. validate buyer inventory capacity for purchases;
4. validate required triggers live immediately before execution;
5. run real-server DSP and Topaz read-only validation against representative schemas;
6. add real database concurrency fixtures with two competing buyers;
7. add append-only audit persistence and redaction tests;
8. keep LIVE typed confirmation and executor feature gating disabled until every gate is proven.
