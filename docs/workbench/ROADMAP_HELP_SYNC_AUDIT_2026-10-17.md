# Roadmap, README, and Help reconciliation — 2026-10-17

Baseline: merged `main` tree `39fb322e5d9d09cb86c01812ae46743559e37cc5`. This is a **source/tree and recent-commit documentation pass**, not a Windows client acceptance test, and not an exhaustive assertion that every one of the repository's modules has been manually exercised.

## Status interpretation

- **Merged implementation** means source is on main; it does not guarantee runtime behavior on a local DSP/Topaz/LSB checkout.
- **Operationally confirmed** requires reproducible client/server observations. Native Ashita movement is reported operational by the operator; independent server-side acceptance is still listed separately.
- **Partial / experimental** labels distinguish research, UX foundations, guarded actions, and still-unverified paths.
- **Historical** applies to dated roadmap snapshots; do not remove those entries or silently convert them to present-day status.

## Reconciliation of important recent areas

| Area | Current merged evidence | Documentation boundary / follow-up |
|---|---|---|
| Live Client / Ashita | Native read/write movement and controls; bridge observation, streaming and multi-entity reconciliation; activity telemetry panel and stable live client picker in recent merged commits | Cross-zone, relog, two-client, headless feed, server-authoritative movement and consistent client-build acceptance still need repeatable operator tests; see `LIVE_CLIENT_DELIVERY_ROADMAP.md` |
| 3D Zone Viewer | Live client selection/zone auto-switch/player centering, multi-DAT geometry for city/ROM2 zones, instance selection, DXT3 alpha correction and headless feed in PR #1045 and subsequent main commits | Validate multi-DAT geometry/alpha per zone, coordinate calibration, instance identity, reconnect and multiple simultaneous entities in actual client |
| GM Command Center | Command categories, ID lookups, targeted player selection, presets/favorites/history, Lua-derived hints and safeguarded opt-in send-to-game; GM documentation PR #1037 | Confirm command semantics against active server; keep dangerous commands confirmation-gated; unknown/blank parameters and quest/mission dropdown refinement remain |
| Calculators | Melee, weapon skill, magic, healing and pet calculators with shared gear selection; RUN/GEO job-grade changes merged in PR #1038 | Mathematical agreement with specific server sources and item/trait datasets requires targeted fixtures; calculations must not be called authoritative game behavior |
| RUN / GEO | Server support is operator-reported; separate toolkit gap-tracker domain merged in PR #1041; job-grade fixes in PR #1040 | **Do not claim these jobs are absent from DSP**. Audit toolkit catalogs/grade coverage and source parity separately from server enablement |
| Voidwalker | Recent merged domain work includes paths/graphs, NM filtering, Abyssea progression, spawn/zone lists and GM testing affordances | Verify source identity, tier/path transitions, Abyssea key item data and cross-lineage behavior locally |
| Assault | Domain tracker and imported Topaz issue/fix-log evidence are present | Tracker/fix-log association is not evidence that an Assault was ported to, enabled on, or validated against DSP; preserve per-instance open status |
| Feature Trace / Behavior Inspector | Evidence dossier, relevance and behavior projections, source/graph paths have extensive merged implementation and audit notes | Relevance/importance ranking, bounded evidence summaries and end-user scenario testing remain distinct from broad node/link retrieval |
| Wiki / translation | Wiki caching, browsing, scrape/import and Japanese translation/client-term support exist | Network-dependent scrape reliability, background import, provenance and local LLM results require run-time acceptance; translation is not primary evidence |
| Auction House / Synth / Key Items | Broad operational UI and guides exist; AH guarded Test-only administration and Key Items indexed DSP Lua evidence are documented | Preserve read-vs-write safety distinction, local schema validation and honest limits on static evidence and ingredient availability |

## Sources and navigation

- GitHub landing page: `README.md`
- **Current capability status:** `docs/workbench/ROADMAP_CURRENT.md`
- Forward-looking guide: `docs/guides/ROADMAP.md`
- Historical implementation ledger: `docs/workbench/ROADMAP.md`, `docs/workbench/AUDIT_STATUS.md`
- In-app status and onboarding: `gui/templates/roadmap.html`, `gui/templates/help.html`
- Module help: `gui/templates/auction_house_help.html`, `gui/templates/capture_help.html`, plus in-module help content.
- Focused docs: `LIVE_CLIENT_DELIVERY_ROADMAP.md`, `LIVE_CLIENT_BRIDGE.md`, `SERVER_GM_COMMAND_CENTER.md`, `FEATURE_TRACE_RELEVANCE_AUDIT_2026-10-11.md`, `KEY_ITEMS_GUIDE.md`, `AUCTION_HOUSE_CAPABILITY_STATUS.md`.

## Documentation hygiene backlog

1. Audit every module's actual page routes and UI controls against its operator guide; add missing dedicated Synth, Assault, RUN/GEO, Voidwalker and calculator help where needed.
2. Check broken links, moved routes, legacy TPZ namespace references, help-page headings and Jinja rendering in automated tests.
3. Expand acceptance records for Ashita/3D, wiki imports, AH writes, synth schema adapters and Key Items active DSP checkout.
4. Keep `ROADMAP_CURRENT.md`, the GUI roadmap and module Help updated in the same PR as substantive functional changes.
5. Consider generating a module-status inventory from registered routes, tests, source docs and release notes to reduce future drift.

This pass intentionally avoids rewriting 100KB+ historical ledgers or declaring untested features complete.
