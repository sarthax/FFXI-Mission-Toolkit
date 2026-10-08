# Spatial cleanup phase 3c47 — reconciliation audit

Audit baseline: `main` at `3c25e99eeb20a985dfc663d42fe5da63ff3f714c`.

## Decision

Do **not** merge `cleanup/spatial-runtime-phase3c47` wholesale.
The branch is 24 commits ahead and 508 behind the inspected main. Its removal of the legacy root spatial entry points was superseded by merged [PR #615](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/615). The narrower [PR #614](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/614) explicitly states that it was superseded by #615.

## Verified findings

- The old branch removes `zone_plot.py` and `build_zone_visual_cache.py`; both are already absent from current main.
- The packaged zone-visual-cache migration test has identical file content across current main and the old branch.
- The branch and main differ in import-path comments/references for `workbench.devtools.domains.nyzul_plot`, `workbench.devtools.spatial.build_visual_cache`, and Zone Editor. Main uses newer packaged interfaces.
- [PR #615](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/615) also retired related editor roots, repointed Item DAT callers, retained editor backup/journal semantics and updated src-layout regressions.

## Not yet independently proven equivalent

The large `src/workbench/app/_host_impl.py` and `gui/templates/zone_plot2.html` files and the Item Editor helper files differ from the old branch. These are not evidence of missing features by themselves; no whole-file replacement or direct cherry-pick is safe. Any suspected missing behavior requires a focused regression against main before implementation.

## Disposition

- `cleanup/spatial-runtime-phase3c47`: mark **SUPERSEDED — RETIRE**; retain until branch deletion is available. No merge.
- `feature/unified-ui-character-editor`: **SUPERSEDED — RETIRE**; its HTML template is byte-identical to main, while main has the newer unified-UI allowlist. No merge.
- `feature/live-client-foundation`: **ACTIVE — PRESERVE**. No changes in this audit.
- Wiki PR #674 remains separate; this audit does not change Wiki code.

## Retirement guard

Before deleting an old branch, check for dependent open PRs and record the final base/head comparison. Branch deletion should not be simulated by forced ref updates.

## Evidence limits

This audit reconciles the known cleanup *intent* against merged PRs and selected file content, but does **not** assert semantic equivalence of every one of the 24 historical commits. Any future regression pointing to a missing behavior should be restored as a new, isolated change on current main with a test.
