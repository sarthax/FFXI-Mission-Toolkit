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
# Present in shipped Help but not in the 322-route GUI_ROUTE_MAP baseline.
# Do not silently call these broken URLs; validate route ownership separately.
UNRESOLVED_INVENTORY = {
    "/auction-house/help", "/live-client/bridge/console", "/synth", "/captures/review",
}
def main():
    route_map = json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP.json").read_text(encoding="utf-8"))
    gets = {r["path"] for r in route_map["routes"] if r["method"] == "GET"}
    seen = set()
    for page in PAGES:
        html = (ROOT / "gui/templates" / page).read_text(encoding="utf-8")
        links = set(re.findall(r"""href=["'](\/[^"'#?{}\s]+)""", html))
        seen.update(links)
        missing = links - gets - UNRESOLVED_INVENTORY
        assert not missing, f"{page}: new Help links absent from route inventory: {sorted(missing)}"
    assert UNRESOLVED_INVENTORY <= seen, "Review and remove stale inventory exceptions"
    print(f"Help static route inventory smoke: PASS ({len(seen)} links; {len(UNRESOLVED_INVENTORY)} follow-ups)")
if __name__ == "__main__":
    main()
