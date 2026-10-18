#!/usr/bin/env python3
"""Feature Catalog schema, source-route and search smoke test."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from workbench.core.services.feature_catalog import load_catalog, search_catalog
from workbench.core.services.feature_catalog_audit import audit_catalog


def main():
    items = load_catalog()
    assert len(items) >= 36
    assert len([f for f in items if f.get('parent_id')]) >= 18
    assert len({f["id"] for f in items}) == len(items)
    routes = json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP.json").read_text())["routes"]
    routes += json.loads((ROOT / "docs/workbench/GUI_ROUTE_MAP_AUXILIARY.json").read_text())["routes"]
    known = {r["path"] for r in routes if r["method"] == "GET"}
    # Dynamic routers are covered by the existing Help route test.
    dynamic = {"/synth", "/auction-house/help", "/live-client/bridge/console"}
    assert all(f["route"] in known | dynamic for f in items), [f["route"] for f in items if f["route"] not in known | dynamic]
    assert all(f["help"] in known | dynamic for f in items)
    assert [f["id"] for f in search_catalog(items, "binary")] == ["client-binary"]
    assert all(f["module"] == "Research & Evidence" for f in search_catalog(items, module="Research & Evidence"))
    audit = audit_catalog()
    assert audit["help_not_cataloged"] == [], audit
    assert audit["invalid_catalog_routes"] == [], audit
    assert "/feature-catalog" in known
    for page in ("help.html", "roadmap.html"):
        assert 'href="/feature-catalog"' in (ROOT / "gui/templates" / page).read_text()
    print("feature catalog smoke: PASS")


if __name__ == "__main__":
    main()
