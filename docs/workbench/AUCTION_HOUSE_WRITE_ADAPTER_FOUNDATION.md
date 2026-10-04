# Auction House Write-Adapter Foundation

This milestone defines the safety contract for future Auction House mutations. It does **not** add an executor or Apply endpoint.

## Guard model

Every future write must be derived from a fresh preview and must carry:

- active named server-environment identity;
- exact DSP/Topaz/LSB-compatible adapter family;
- deterministic snapshot fingerprint;
- required table and trigger inventory;
- semantic mutation steps rather than free-form SQL;
- an audit intent containing target, before-state, expected after-state, environment, and adapter family;
- explicit LIVE confirmation by typing the active profile name exactly;
- transaction-time re-read and stale-state rejection;
- rollback on any error;
- append-only audit only after a successful commit.

Legacy fallback environments are intentionally preview-only until migrated to a named environment.

## LandSandBoat trigger dependency

Current LandSandBoat treats Auction House and delivery-box triggers as required database behavior. The write-contract foundation therefore requires:

- listing: `auction_house_list`;
- purchase/cleanup: `auction_house_buy` and `delivery_box_insert`;
- `delivery_box` table availability for purchase/cleanup planning.

The toolkit must not model seller proceeds as a direct `chars.gil` edit. Auction House proceeds and delivery semantics must be preserved through the verified lineage contract.

## Current implementation

`src/workbench/server_admin/auction_house/write_plans.py` provides deterministic, non-executable plans for:

- single-item listing;
- normal purchase;
- administrative cleanup purchase.

Each plan exposes `contract_ready`, `executor_enabled`, and `executable`. `executor_enabled` is hard-coded false in this milestone, so no plan can become executable even when every schema/environment check passes.

The plan stores no executable INSERT/UPDATE/DELETE SQL. Mutation steps are descriptive until lineage-specific behavior is proven by fixtures and representative server generations.

## Next gate before Apply

Before enabling the first write operation:

1. inventory live table/trigger presence from the active DB;
2. prove LSB listing and buy trigger semantics against current schema fixtures;
3. prove DSP/Topaz historical behavior separately instead of inheriting LSB assumptions;
4. implement a transaction executor behind an explicit approval token;
5. re-read the exact target rows inside the transaction and compare the preview fingerprint;
6. commit or rollback atomically;
7. append Auction House-specific audit history after commit;
8. expose Apply in the GUI only after those tests are green.
