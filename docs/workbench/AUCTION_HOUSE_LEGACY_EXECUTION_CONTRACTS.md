# Auction House Legacy Execution Contracts

## Status

DSP and Topaz Auction House source semantics are verified, and the toolkit now has an explicit **non-executable execution-contract specification** for those lineages.

This does **not** enable writes. The Auction House executor remains disabled.

## Listing contract

A future DSP/Topaz listing adapter must perform the complete operation under one transaction and must:

- re-read item, seller, inventory and active-listing state;
- reject a stale preview or changed auctionability state;
- re-check the legacy listing limit;
- calculate the lineage-correct listing fee;
- insert exactly one active Auction House row;
- remove exactly one item or one full stack as represented by the listing;
- debit the verified listing fee exactly once;
- verify the resulting row/inventory/gil state before commit;
- roll back the whole operation on any invariant failure;
- append an immutable administrative audit record after commit.

## Purchase / cleanup contract

A future DSP/Topaz purchase adapter must:

- re-read the exact previewed Auction House row inside the transaction;
- reject sold, cancelled, changed or missing rows;
- preserve cheapest-qualifying-row behavior for a normal purchase;
- atomically claim at most one active listing so two buyers cannot purchase the same row;
- update buyer, sale value and sale timestamp using the verified legacy semantics;
- grant the exact listed item/stack once;
- debit buyer gil exactly once for a normal purchase;
- preserve `auction_house_buy` and `delivery_box_insert` seller settlement;
- never replace seller settlement with a direct `chars.gil` edit;
- verify auction, buyer and delivery-box post-state before commit;
- roll back all mutation state if any pre-commit invariant fails.

## Stale-preview protection

The deterministic preview fingerprint is an authorization boundary, not a convenience cache. A future executor must re-read all mutation-relevant rows and reject the request if those values no longer match the previewed state. It must never silently refresh and continue with a changed target.

A plan must also be rejected if it was produced for another environment or another explicit lineage.

## Concurrency requirements

Regression coverage for the implementation phase must prove that:

- the same `auction_id` cannot be successfully claimed twice;
- competing buyers produce at most one successful purchase;
- cheapest-qualifying-row semantics remain correct under competition;
- listing-limit checks cannot be bypassed by concurrent listings.

## Rollback requirements

Failure of inventory mutation, gil mutation, Auction House state change, seller delivery-box triggers, or post-state verification must roll back the owning transaction.

Audit persistence occurs after the database commit. If audit persistence fails after a successful commit, the toolkit must report an integrity alert and must **not** replay the mutation.

## Remaining gates before any executor can exist

1. Implement a lineage-specific transactional adapter without a free-form SQL entry path.
2. Add representative live-schema integration fixtures for DSP and Topaz.
3. Prove two-buyer concurrency behavior.
4. Prove stale-preview rejection for listing and purchase.
5. Prove rollback across Auction House, inventory/gil and delivery-box failure paths.
6. Implement append-only audit persistence with credential/secret redaction.
7. Complete real-server validation for both lineages.
8. Only then consider a separately reviewed executor feature flag and mutation routes.

Until every applicable gate is completed, DSP/Topaz remain preview-only and `executor_permitted` remains false.
