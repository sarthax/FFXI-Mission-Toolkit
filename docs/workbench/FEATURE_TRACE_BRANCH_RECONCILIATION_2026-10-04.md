# Feature Trace branch reconciliation — 2026-10-04

This note records reconciliation of the remaining Feature Trace branches against current `main`.

## Fully represented in `main`

- `feature-trace-diagnosis-benchmarks` — no unique commits remain.
- `feature-trace-gui-modes` — no unique commits remain.

These branches are stale branch references only.

## Superseded

- `feature-trace-scenario-ui` — the alternate scenario-page implementation was superseded by the merged focused modes/provider-evidence integration in the existing Feature Trace page (PRs #448/#449; PR #450 was closed for that reason). No code is transplanted from this branch.

## Transplanted and merged

The unique `feature-trace-drop-chain-benchmarks` work was reviewed commit-by-commit and transplanted onto current `main` rather than merged wholesale.

Preserved capabilities:

- explicit read-only `mob_droplist` catalog identity using the complete source row because upstream schemas do not provide a stable primary key;
- deterministic `mob_groups.dropid -> mob_droplist` expansion;
- deterministic `mob_droplist.itemId -> item_basic` expansion;
- item/drop vocabulary in focused Feature Trace modes;
- executable scenario benchmark contracts;
- end-to-end notorious-monster benchmark proving spawn -> group -> pool/drop -> item navigation without writing canonical graph edges.

The transplant deliberately preserves newer `main` work that did not exist on the old branch, including later provider links, instance/entity relationships, pet/pool relationships, wiki alignment links, and other fail-closed provider behavior.

The transplant merged through PR #474 after Workbench Regression and Src Layout Regression passed. The old `feature-trace-drop-chain-benchmarks` branch and the temporary transplant branch are therefore superseded/stale references; the merged `main` implementation is authoritative.
