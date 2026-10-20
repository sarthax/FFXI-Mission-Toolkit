"""Read-only catalog coverage diagnostics for static Help links and route inventory."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from workbench.core.services.feature_catalog import ROOT, load_catalog

LINK = re.compile(r"""href=["'](\/[^"'#?{}\s]+)""")
DYNAMIC_ROUTES = frozenset({"/synth", "/auction-house/help", "/live-client/bridge/console", "/feature-testing"})
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
    # Inventory is a candidate pool, not an automatic feature generator.
    # Legacy and merge-target pages remain visible for manual classification.
    page_routes = {row["path"]: row.get("disposition", "UNKNOWN")
                   for name in ("GUI_ROUTE_MAP.json", "GUI_ROUTE_MAP_AUXILIARY.json")
                   for row in json.loads((root / "docs/workbench" / name).read_text(encoding="utf-8"))["routes"]
                   if row["method"] == "GET" and row.get("role") == "page"
                   and "{" not in row["path"] and row["path"] not in {"/", "/help", "/roadmap", "/feature-catalog"}}
    uncovered = sorted(path for path, disposition in page_routes.items()
                       if path not in catalog_routes and disposition not in {"LEGACY", "MERGE"})
    # Completeness is separate from implemented status and route coverage.
    # Flag genuinely missing operator detail, not a matching summary/purpose.
    parent_ids={row["parent_id"] for row in features if row.get("parent_id")}
    child_counts={row["id"]:sum(child.get("parent_id")==row["id"] for child in features)
                  for row in features if row["id"] in parent_ids}
    missing_operator_detail={
        row["id"]:[key for key in ("purpose","how_to_use","caveat")
                   if not isinstance(row.get(key),str) or not row[key].strip()]
        for row in features
        if any(not isinstance(row.get(key),str) or not row[key].strip()
               for key in ("purpose","how_to_use","caveat"))
    }
    status_totals={
        "implementation":{state:sum(f["implementation"]==state for f in features)
                          for state in ("implemented","partial","research","planned")},
        "validation":{state:sum(f["validation"]==state for f in features)
                      for state in ("unverified","operator_reported","tested")},
    }
    help_coverage = {
        "contextual": sorted(f["id"] for f in features if f["help"].startswith("/help#")),
        "generic": sorted(f["id"] for f in features if f["help"] == "/help"),
        "module_specific": sorted(f["id"] for f in features
                                  if not f["help"].startswith("/help")),
    }
    help_coverage["counts"] = {k: len(help_coverage[k])
                               for k in ("contextual", "generic", "module_specific")}
    help_coverage["generic_by_module"] = {
        module: sorted(f["id"] for f in features if f["module"] == module and f["help"] == "/help")
        for module in sorted({f["module"] for f in features})
        if any(f["module"] == module and f["help"] == "/help" for f in features)
    }
    return {
        "feature_count": len(features),
        "help_coverage": help_coverage,
        "module_count": len({f["module"] for f in features}),
        "subfeature_count": sum(bool(f.get("parent_id")) for f in features),
        "status_totals": status_totals,
        "missing_operator_detail": missing_operator_detail,
        "module_function_counts": child_counts,
        "help_routes": len(help_routes),
        "help_not_cataloged": sorted(help_routes - catalog_routes),
        "catalog_not_help_linked": sorted(catalog_routes - help_routes),
        "invalid_catalog_routes": sorted(catalog_routes - routes),
        "uncataloged_active_pages": uncovered,
        "excluded_legacy_or_merge_pages": sorted(path for path, disposition in page_routes.items()
                                                   if path not in catalog_routes and disposition in {"LEGACY", "MERGE"}),
        "unverified_features": sorted(f["id"] for f in features if f["validation"] == "unverified"),
        "note": "Active page coverage excludes parameterized, LEGACY and MERGE-disposition pages. It is not exhaustive subfeature or runtime coverage.",
    }
