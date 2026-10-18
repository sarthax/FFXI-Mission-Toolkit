"""Read-only catalog coverage diagnostics for static Help links and route inventory."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from workbench.core.services.feature_catalog import ROOT, load_catalog

LINK = re.compile(r"""href=["'](\/[^"'#?{}\s]+)""")
DYNAMIC_ROUTES = frozenset({"/synth", "/auction-house/help", "/live-client/bridge/console"})
EXCLUDED = frozenset({"/roadmap", "/feature-catalog"})


def audit_catalog(root: Path = ROOT) -> dict:
    features = load_catalog(root / "feature_catalog" / "features.json")
    help_text = (root / "gui/templates" / "help.html").read_text(encoding="utf-8")
    help_routes = {html.unescape(route) for route in LINK.findall(help_text)} - EXCLUDED
    routes = set()
    for name in ("GUI_ROUTE_MAP.json", "GUI_ROUTE_MAP_AUXILIARY.json"):
        payload = json.loads((root / "docs/workbench" / name).read_text(encoding="utf-8"))
        routes.update(row["path"] for row in payload["routes"] if row["method"] == "GET")
    routes |= DYNAMIC_ROUTES
    catalog_routes = {f["route"] for f in features}
    return {
        "feature_count": len(features),
        "help_routes": len(help_routes),
        "help_not_cataloged": sorted(help_routes - catalog_routes),
        "catalog_not_help_linked": sorted(catalog_routes - help_routes),
        "invalid_catalog_routes": sorted(catalog_routes - routes),
        "unverified_features": sorted(f["id"] for f in features if f["validation"] == "unverified"),
        "note": "Route coverage is a navigation proxy, not exhaustive subfeature coverage or runtime acceptance.",
    }
