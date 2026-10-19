#!/usr/bin/env python3
"""Feature Catalog schema, source-route and search smoke test."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workbench.core.services.feature_catalog import load_catalog, search_catalog, feature_detail
from workbench.core.services.feature_catalog_audit import audit_catalog
from workbench.core.services.feature_catalog_gui_audit import audit_gui_controls
from workbench.core.services.feature_catalog_gui_inventory import inventory_gui, discover_controls


def main():
    items = load_catalog()
    assert len(items) >= 75
    assert all(f.get("purpose") and f.get("how_to_use") and f.get("caveat") for f in items)
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
    capture = feature_detail(items, "capture-browser")
    assert len(capture["children"]) >= 10
    assert all(child.get("how_to_use") and child.get("purpose") and child.get("caveat")
               for child in capture["children"])
    for module_id in ("auction-house", "live-client", "feature-trace", "wiki"):
        children = feature_detail(items, module_id)["children"]
        assert children, module_id
        assert all(child.get("how_to_use") and child.get("purpose") for child in children), module_id
    assert feature_detail(items, "retail-versions-browse")["parent"]["id"] == "retail-versions"
    assert len(feature_detail(items, "client-binary")["children"]) >= 5
    assert len(feature_detail(items, "retail-versions")["children"]) >= 5
    assert all(f.get("how_to_use") and f.get("caveat")
               for f in feature_detail(items, "client-binary")["children"])
    assert feature_detail(items, "missing-capability") is None
    assert "auction-house" in {f["id"] for f in search_catalog(items, "guarded")}
    assert all(f["module"] == "Research & Evidence" for f in search_catalog(items, module="Research & Evidence"))
    audit = audit_catalog()
    gui_audit = audit_gui_controls()
    inventory = inventory_gui()
    assert inventory["control_count"] > 0
    assert any(p["controls"] for p in inventory["pages"])
    assert discover_controls('<button type="submit">Run test</button><a href="/help">Help</a>') == [
        {"kind": "button", "label": "Run test", "target": ""},
        {"kind": "a", "label": "Help", "target": "/help"}]

    assert gui_audit["sample_count"] >= 29
    assert len(gui_audit["pages"]) >= 9
    assert gui_audit["missing"] == [], gui_audit["missing"]
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
                         q="", module="", coverage=audit, detail=details, gui_audit=gui_audit, gui_inventory=inventory)
    assert "GUI control coverage audit" in detail_page
    assert "Automatic GUI control candidates" in detail_page
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
