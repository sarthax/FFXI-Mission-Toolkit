# Help navigation and route inventory audit — 2026-10-18

Scope: literal local `href="/..."` links in global Help, in-app Roadmap, Capture Help and Auction House Help, compared to GET records in `docs/workbench/GUI_ROUTE_MAP.json` (322-route baseline). Template-built JS URLs, parameterized routes, redirects, auth gates and actual HTTP responses are **not** checked here.

## Initial results

- Global Help: `/auction-house/help`, `/live-client/bridge/console`, and `/synth` link to pages **absent from the static GET inventory**.
- In-app Roadmap: the same three inventory discrepancies.
- Capture Help: `/captures/review` is absent from the static GET inventory.
- Other literal links in these four pages match GET routes in the inventory.

**These are not confirmed broken links.** The pages and implementation may be registered via different route-mounting mechanisms, and the static map may be incomplete. Before resolving, inspect actual host/router registration and verify HTTP status after boot; either register them in the authoritative inventory or change obsolete Help URLs if proven wrong.

## Follow-up

1. Confirm whether the four paths are operational GET endpoints using local app startup/route enumeration.
2. Expand the link auditor to dynamic Jinja destinations, sidebar navigation and JS-generated links without false positives.
3. Maintain exception list only for verified intentional routes; remove exceptions once `GUI_ROUTE_MAP.json` is complete.
4. Keep the smoke check in CI and avoid describing missing inventory entries as runtime 404s.

A curated check runs as `test_fixtures/test_help_route_inventory.py`.

## Source follow-up (2026-10-18)

The maintained `GUI_ROUTE_MAP_AUXILIARY.json` has an explicit GET entry for `/captures/review`; the CI smoke test now uses both inventories and removes that exception. The source also exposes `@router.get("/auction-house/help")` in `src/workbench/server_admin/auction_house/status_ui.py` and `@router.get("/synth")` in `src/workbench/server_admin/synth/api.py`. These two are present as route handlers even though not listed in the combined static route map; final router inclusion and live HTTP responses still require verification. `/live-client/bridge/console` is supported by an existing HTTP 200 integration test in `tests/test_live_client_bridge_management_api.py`; live environment setup remains a separate acceptance concern. The three remaining inventory exceptions represent **inventory completeness** follow-ups, not established broken links.
