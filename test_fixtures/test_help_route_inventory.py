#!/usr/bin/env python3
"""Check static in-app Help links against the maintained GET route inventory.

Unregistered-in-inventory does not mean unavailable at runtime: exceptions are
explicitly documented until route registration is checked independently.
"""
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PAGES = ("help.html", "roadmap.html", "capture_help.html", "auction_house_help.html")
# These routes are served by dynamically registered module routers.
MODULE_ROUTES = {
    "/auction-house/help": ("src/workbench/server_admin/auction_house/status_ui.py", '@router.get("/auction-house/help"', "auction_house_status_router"),
    "/synth": ("src/workbench/server_admin/synth/api.py", '@router.get("/synth"', "synth_router"),
}
def main():
    route_map = json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP.json").read_text(encoding="utf-8"))
    auxiliary = json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP_AUXILIARY.json").read_text(encoding="utf-8"))
    gets = {r["path"] for inventory in (route_map, auxiliary) for r in inventory["routes"] if r["method"] == "GET"}
    integration = (ROOT / "src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    for route, (source, marker, router_name) in MODULE_ROUTES.items():
        assert marker in (ROOT / source).read_text(encoding="utf-8"), f"Missing handler: {route}"
        assert router_name in integration, f"Missing module registration: {route}"
        gets.add(route)
    bridge_src = (ROOT / "src/workbench/runtime/live_client/bridge_management_api.py").read_text(encoding="utf-8")
    assert "/live-client/bridge/console" in bridge_src
    bridge_test = (ROOT / "tests/test_live_client_bridge_management_api.py").read_text(encoding="utf-8")
    assert 'client.get("/live-client/bridge/console")' in bridge_test
    assert 'assert html.status_code == 200' in bridge_test
    gets.add("/live-client/bridge/console")
    seen = set()
    for page in PAGES:
        html = (ROOT / "gui/templates" / page).read_text(encoding="utf-8")
        links = set(re.findall(r"""href=["'](\/[^"'#?{}\s]+)""", html))
        seen.update(links)
        missing = links - gets
        assert not missing, f"{page}: new Help links absent from route inventory: {sorted(missing)}"
    print(f"Help static route inventory smoke: PASS ({len(seen)} links; module handlers checked)")
if __name__ == "__main__":
    main()
