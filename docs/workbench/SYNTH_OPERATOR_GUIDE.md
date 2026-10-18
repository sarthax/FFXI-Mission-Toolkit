# Synth & Crafting — operator guide

This page documents the `/synth` workbench visible on the merged application. The **active named environment** and the detected recipe-schema family determine which data can be read or changed.

## Before working

1. In Settings, select and verify the intended server environment. Confirm the active profile displayed on the Synth page.
2. For analysis, remain on the read-only tabs. For edits, use a non-production/test environment and confirm the page's available controls, previews and write safeguards before applying anything.
3. Distinguish **database/source evidence** from proven in-game recipe behavior: ingredient existence, name mapping and source availability do not prove obtainability, vendor stock or successful synthesis.

## Tabs

| Tab | Operator workflow | Risk / interpretation |
|---|---|---|
| **Recipes** | Search by result or ingredient, craft, skill range or synth/desynth; select a recipe to inspect ingredients and missing-source indicators. | Read-only discovery. “Only incomplete” applies to the currently displayed page and is not a complete global status by itself. |
| **Audit** | Run a recipe audit; examine flagged recipe rows; export CSV; investigate vendor gaps and naming/guild research. | A heuristic warning requires source inspection; it is not automatically a confirmed server defect. |
| **Health** | Run structural and source-coverage checks. | A successful schema check does not prove a real crafting attempt will succeed. |
| **Compare** | Compare recipe representations across configured sources/environments. | Evaluate schema and item-ID drift before applying any conversion. |
| **Economy** | Inspect synthesis inputs/outputs in economy context where data is available. | Listings or vendor prices are observations, not a guaranteed arbitrage outcome. |
| **Editor** | Modify supported recipe fields using the page's editor workflow. | **Potentially mutating**. Confirm active environment, schema compatibility and preview/validation controls; do not assume read-only because adjacent tabs are read-only. |
| **Export / Port** | Generate and copy portable SQL for review and downstream porting. | Generated SQL is a proposal; review target columns, item IDs, requirements and data differences before external execution. |

## Operational verification checklist

- Confirm expected recipes and crystals/ingredients against the checkout's `synth_recipes` schema.
- Check a representative normal synthesis, desynthesis, HQ outcome, skill restriction and key-item requirement.
- For any mutating test, record original row values, candidate diff, intended target profile, post-change row, and rollback route.
- Validate exported SQL against a separate target schema; never assume source and destination IDs match.
- Preserve the exact source file/DB row and environment used for every discrepancy report.

## Related surfaces

- Root README: `README.md`
- Current capability status: `docs/workbench/ROADMAP_CURRENT.md`
- Documentation reconciliation: `docs/workbench/ROADMAP_HELP_SYNC_AUDIT_2026-10-17.md` (landed separately in PR #1047)
- Auction House operator guidance: `/auction-house/help`

This guide reflects visible UI capabilities. It is not a claim that DSP, Topaz, LandSandBoat and custom forks share identical edit semantics, or that every mutation path has been validated against a live database.
