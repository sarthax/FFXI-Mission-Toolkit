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
