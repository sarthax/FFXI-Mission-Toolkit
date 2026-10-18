#!/usr/bin/env python3
"""Feature Catalog schema, source-route and search smoke test."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workbench.core.services.feature_catalog import load_catalog, search_catalog, feature_detail
from workbench.core.services.feature_catalog_audit import audit_catalog


def main():
    items = load_catalog()
    assert len(items) >= 75
    assert len([f for f in items if f.get('parent_id')]) >= 18
    assert len({f["id"] for f in items}) == len(items)
    routes = json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP.json").read_text())["routes"]
    routes += json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP_AUXILIARY.json").read_text())["routes"]
    known = {r["path"] for r in routes if r["method"] == "GET"}
    # Dynamic routers are covered by the existing Help route test.
    dynamic = {"/synth", "/auction-house/help", "/live-client/bridge/console"}
    assert all(f["route"] in known | dynamic for f in items), [f["route"] for f in items if f["route"] not in known | dynamic]
    assert all(f["help"] in known | dynamic for f in items)
    assert "client-binary" in {f["id"] for f in search_catalog(items, "binary")}
    details = feature_detail(items, "auction-house")
    assert details["feature"]["how_to_use"]
    assert details["children"]
    assert feature_detail(items, "missing-capability") is None
    assert "auction-house" in {f["id"] for f in search_catalog(items, "guarded")}
    assert all(f["module"] == "Research & Evidence" for f in search_catalog(items, module="Research & Evidence"))
    audit = audit_catalog()
    assert audit["help_not_cataloged"] == [], audit
    assert audit["invalid_catalog_routes"] == [], audit
    assert audit["uncataloged_active_pages"] == [], audit
    # Render the actual Jinja page through the existing GUI shell fixture.
    # This checks template inheritance, context keys, filtering, and coverage UI.
    from test_gui_shell import render
    page = render("feature_catalog.html", "/feature-catalog",
                  features=items, modules=sorted({f["module"] for f in items}),
                  q="", module="", coverage=audit)
    assert "Coverage audit" in page
    assert "uncataloged active pages" in page
    assert "Feature Trace" in page
    assert "Feature Catalog" in page
    detail_page = render("feature_catalog.html", "/feature-catalog",
                         features=items, modules=sorted({f["module"] for f in items}),
                         q="", module="", coverage=audit, detail=details)
    assert "Functions in this module" in detail_page
    assert "How to use" in detail_page
    assert "/feature-catalog?feature=" in detail_page
    filtered = search_catalog(items, "binary")
    filtered_page = render("feature_catalog.html", "/feature-catalog",
                           features=filtered, modules=sorted({f["module"] for f in items}),
                           q="binary", module="", coverage=audit)
    assert "Binary Inspector" in filtered_page
    assert "No matching capabilities." not in filtered_page
    assert "/feature-catalog" in known
    from workbench.gui_shell import WORKSPACES
    assert any(section.get("href") == "/feature-catalog"
               for workspace in WORKSPACES for section in workspace["sections"])
    for page in ("help.html", "roadmap.html"):
        assert 'href="/feature-catalog"' in (ROOT / "gui/templates" / page).read_text()
    print("feature catalog smoke: PASS")


if __name__ == "__main__":
    main()
