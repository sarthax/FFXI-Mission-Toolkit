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

## Five calculator page handlers — source verification

All five calculators listed in the sidebar have explicit GET page handlers in their respective module source:

| Sidebar route | Source |
| --- | --- |
| `/tools/ws-calc` | `src/workbench/server_admin/wscalc/router.py` |
| `/tools/melee-calc` | `src/workbench/server_admin/meleecalc/router.py` |
| `/tools/magic-calc` | `src/workbench/server_admin/wscalc/magic_router.py` |
| `/tools/heal-calc` | `src/workbench/server_admin/healcalc/router.py` |
| `/tools/pet-calc` | `src/workbench/server_admin/petcalc/router.py` |

This narrows five of the 22 static inventory discrepancies to **defined source routes**, not established 404s. Runtime mounting, full template rendering, and numerical correctness still require separate validation. The other unlisted domain and character/editor/viewer routes remain unresolved by this pass.

## Parameterized host-route reconciliation (2026-10-18)

The 14 domain category sidebar URLs are backed by one source handler, `@app.get("/domains/{key}")` in `src/workbench/app/_host_impl.py`, and all 14 corresponding keys exist in `src/workbench/domains/definitions.json`. This demonstrates route-pattern and catalog coverage, **not** a successful live HTTP response for every domain.

The 3D Viewer uses `@app.get("/zones/{zoneid}/view3d")`; `/zones/0/view3d` is a concrete sidebar example of that parameterized route. This establishes a route pattern but does not prove a zone 0 mesh is usable.

The Character Editor mounts `src/workbench/editors/character/gui.py` through `app.include_router(character_editor_router)`; its prefix is `/character-editor`, and the page's `@router.get("")` forms the exact sidebar root.

`test_fixtures/test_dynamic_sidebar_routes.py` now guards these source contracts and all 14 domain definition keys. With five calculator handlers and the replay-console source previously confirmed, **all 22 original sidebar inventory discrepancies have identifiable route source definitions or registered category keys**. The remaining work is route-map generation from the mounted app and an HTTP smoke test with runtime prerequisites; do not confuse source evidence with successful page rendering.

## Mounted route smoke test — proposed 2026-10-18

`test_fixtures/test_mounted_sidebar_routes.py` imports the real `workbench.app.host:app` and checks the final GET route table for the domain, character editor, 3D viewer, replay/bridge, AH/Synth/Capture and calculator page patterns. It also verifies fourteen domain configuration keys. This is stronger than searching static strings. CI execution is required before considering this test passed; it deliberately does not render pages, connect to DSP or command the client.

**CI portability caveat (2026-10-18):** The mounted-app smoke needs the compiled `xi_tinkerer` package when importing `workbench.app.host`. The Linux core regression runner does not contain that native wheel. The smoke explicitly reports **NOT RUN** and exits without claiming mounted-route acceptance when the package is missing; the earlier static-source route checks continue to run. Run the mounted smoke in an installed Toolkit environment with `xi_tinkerer` and all runtime dependencies to obtain a real PASS. An HTTP test remains separate.
