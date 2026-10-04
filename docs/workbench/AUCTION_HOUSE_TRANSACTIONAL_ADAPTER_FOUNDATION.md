# Auction House Transactional Adapter Foundation

This layer is the bridge between the DSP/Topaz execution-contract specification and a future database-backed adapter. It is deliberately non-executable.

## What it provides

- Explicit DSP/Topaz adapter-family and schema-shape validation.
- Active-environment and lineage matching.
- Preview-environment pinning so a plan cannot cross server environments.
- Deterministic preview/current-state fingerprint comparison.
- Stale-preview rejection.
- Purchase claim-cardinality validation.
- Cheapest-qualifying-listing validation for normal purchases.
- An in-memory rollback simulation harness for auction, inventory, gil, and delivery fixture states.
- A hard `executor_enabled = false` / `executable = false` contract.

## What it does not provide

- No database write primitive.
- No SQL mutation statements.
- No transaction `commit()` path.
- No `/apply` or `/commit` HTTP endpoint.
- No executor feature flag.
- No authorization to modify DSP, Topaz, LSB, or custom-fork databases.

## Remaining gates

1. Build lineage-specific **database-backed reread adapters** that can collect the exact mutation-relevant state inside a transaction without yet committing mutations.
2. Add representative DSP and Topaz schema fixtures, including inventory and delivery-box table variations found in real servers.
3. Add a two-connection concurrency harness proving only one buyer can claim an auction and normal purchase preserves cheapest-qualifying-row behavior.
4. Add real transaction rollback integration tests covering auction row, inventory, gil, and delivery-box trigger failures.
5. Add append-only audit persistence with credential/redaction tests.
6. Validate against real DSP and Topaz test servers.
7. Only after all gates pass should a separately reviewed executor implementation be considered.

The presence of this foundation must never be interpreted as write readiness. It validates candidate state and fixture behavior only.
