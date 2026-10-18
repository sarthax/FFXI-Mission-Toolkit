# Sidebar route inventory reconciliation — 2026-10-18

Reviewed the literal `href` entries in `src/workbench/gui_shell.py` on the merged `main` baseline, normalizing fragment/query suffixes, against the combined GET route lists in `GUI_ROUTE_MAP.json` and `GUI_ROUTE_MAP_AUXILIARY.json`.

- 121 literal sidebar destination occurrences, representing 71 distinct normalized paths.
- 22 distinct sidebar paths are absent from **both** route inventories. This is an inventory discrepancy, **not** a confirmed browser 404.
- Many domain destinations are category pages and may be composed dynamically. The registered route patterns and runtime host should be checked before editing navigational links.

## Missing from combined static inventories

### Domain destinations
`/domains/abyssea`, `/domains/battlefields`, `/domains/conflict`, `/domains/combat`, `/domains/dynamis`, `/domains/escha`, `/domains/hobbies`, `/domains/helm`, `/domains/events`, `/domains/missions`, `/domains/quests`, `/domains/roe`, `/domains/trust`, `/domains/other`.

### Other sidebar destinations
`/character-editor`, `/zones/0/view3d`, `/live-client/replay/console`, `/tools/ws-calc`, `/tools/melee-calc`, `/tools/magic-calc`, `/tools/heal-calc`, `/tools/pet-calc`.

## Recommended validation

1. Enumerate the actual `FastAPI.app.routes` **after** all module bridges and domain routers are mounted; match literal paths as well as parameterized routes and redirects.
2. Separate callable page destinations, computed URLs and category fragment anchors, preserving query semantics.
3. For each category, exercise HTTP GET with a minimal configured test host; record missing prerequisites separately from 404.
4. Reconcile the route maps from registered application routes, rather than adding static entries purely to satisfy a documentation test.
5. Only after resolution, extend the CI link check to the complete sidebar. Do not hard-fail on these 22 unknowns before registration is verified.

This inventory is from static repository source, not a running Windows client.

## Verified source contracts — follow-up

- `/live-client/replay/console`: `create_replay_console_router` creates an APIRouter with prefix `/live-client/replay` and a GET `/console` handler; `tests/test_live_client_replay_console.py` also checks HTTP 200. It is not merely an invented sidebar path.
- `/tools/ws-calc`: `create_wscalc_router` defines `@r.get("/tools/ws-calc")` in `src/workbench/server_admin/wscalc/router.py`. Confirm actual host inclusion separately.
- The other calculator and domain destinations, plus `/zones/0/view3d` and `/character-editor`, remain pending a systematic mounted-router audit; do not mark them broken from inventory absence.

The distinction is between **defined route**, **mounted route**, **renderable response** and **actual runtime behavior**. Those are four separate validation levels.
