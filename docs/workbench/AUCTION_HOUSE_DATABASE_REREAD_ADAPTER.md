# Auction House database reread adapter

This slice adds the first database-backed portion of the guarded DSP/Topaz write path without enabling writes.

The adapter:

- starts `START TRANSACTION READ ONLY`;
- rereads the item/seller or auction/buyer snapshot used by the preview fingerprint;
- captures seller/buyer gil, seller active-listing count, relevant inventory rows, seller delivery-box rows, and the current cheapest qualifying auction;
- feeds the fresh snapshot into the existing stale-preview/concurrency validator;
- always rolls the read-only transaction back;
- contains no mutation SQL and has no commit path.

The extra inventory/gil/listing-count/delivery evidence is intentionally kept outside the preview fingerprint for now. The fingerprint remains bound to the same normalized preview snapshot shape, while the additional state becomes input to the next validation layer.

## Remaining gates

1. Normalize lineage-specific inventory and delivery-box schema variations against real DSP/Topaz databases.
2. Add invariant checks for listing quantity, seller gil/listing fee, buyer funds, listing limits, and delivery-box capacity.
3. Add real database concurrency fixtures for competing buyers.
4. Add append-only audit persistence.
5. Only after real-server validation, design a mutation adapter behind a separate explicit execution gate.

No Apply/Commit endpoint or executor feature flag is introduced here.
