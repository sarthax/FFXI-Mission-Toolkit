# Auction House unified preview validation

The legacy DSP/Topaz Auction House administration path now has a single read-only validation orchestrator for preview safety evidence.

## Ordered validation stages

1. Active named server environment and explicit lineage.
2. Source-backed lineage/schema agreement.
3. Live Auction House table/trigger prerequisites.
4. Fresh database reread and stale-preview/concurrency checks.
5. Active Auction House configuration load.
6. Preview policy-fingerprint/source/family binding.
7. Listing or purchase economic/inventory/settlement invariants.

The orchestrator returns each stage separately plus a flattened blocker list so an administrator can see exactly why a preview is blocked.

## Status model

`read_only_validation_ready` means all live evidence gates above are healthy. It does **not** authorize a write.

`execution_ready`, `executor_enabled`, and `write_enabled` are always `false` in this phase.

DSP/Topaz retain `lineage_execution_contract_incomplete` as an execution blocker even when the complete read-only evidence chain is healthy. The report deliberately exposes both facts at once: administrators can distinguish a healthy preview from an enabled executor.

## Fail-closed behavior

The report is blocked for stale database state, policy drift, missing policy binding, wrong environment, schema/trigger gaps, invalid inventory/fees/funds/settlement state, or any earlier gate that prevents invariant evaluation.

The current one-call orchestrator is intentionally scoped to explicit DSP and Topaz environments because the active-config/policy-binding path is legacy-specific. LSB is reported as unsupported by this orchestrator rather than being silently evaluated with legacy assumptions.

## Safety

The report performs no Auction House mutation and contains no commit/apply path. It only composes existing read-only probes and validation evidence. A presentation endpoint/UI may consume this report later without changing the execution state.
