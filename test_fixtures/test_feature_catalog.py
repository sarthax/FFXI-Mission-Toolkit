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
    dynamic = {"/synth", "/auction-house/help", "/live-client/bridge/console", "/feature-testing"}
    assert all(f["route"] in known | dynamic for f in items), [f["route"] for f in items if f["route"] not in known | dynamic]
    assert all(f["help"].split("#", 1)[0] in known | dynamic for f in items)
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
    testing = feature_detail(items, "feature-testing")
    assert testing and len(testing["children"]) >= 3
    assert all(child.get("how_to_use") and child.get("caveat") for child in testing["children"])
    assert feature_detail(items, "trace-wiki-provenance")["parent"]["id"] == "feature-trace"
    assert feature_detail(items, "wiki-source-navigation")["parent"]["id"] == "wiki"
    assert len(feature_detail(items, "key-items")["children"]) >= 4
    assert len(feature_detail(items, "validation")["children"]) >= 2
    for subfeature_id in ("ki-mapping-comparison", "ki-operation-dependencies",
                          "ki-evidence-handoff", "validation-run-history",
                          "validation-live-target"):
        detail = feature_detail(items, subfeature_id)
        assert detail["parent"] and detail["feature"]["how_to_use"]
        assert detail["feature"]["validation"] == "unverified"
    for feature_id in ("feature-trace", "trace-evidence", "trace-wiki-provenance",
                       "feature-testing", "testing-scenario-builder", "testing-run-inspector",
                       "testing-supervisor", "key-items", "ki-operation-dependencies"):
        entry = feature_detail(items, feature_id)["feature"]
        assert entry.get("source_refs") and entry.get("test_refs"), feature_id
        assert entry["validation"] != "tested", feature_id
    help_html = (ROOT / "gui/templates/help.html").read_text(encoding="utf-8")
    for feature in items:
        if "#" in feature["help"]:
            fragment=feature["help"].split("#", 1)[1]
            assert f'id="{fragment}"' in help_html, feature["id"]
    assert feature_detail(items, "feature-testing")["feature"]["help"] == "/help#help-feature-testing"
    assert feature_detail(items, "capture-browser")["feature"]["source_refs"] == ["gui/templates/captures.html"]
    bridge = feature_detail(items, "live-bridge")["feature"]
    assert "tests/test_live_client_bridge_protocol.py" in bridge["test_refs"]
    assert bridge["validation"] == "unverified"
    for feature_id in ("entity-lookup", "sql-browser"):
        entry = feature_detail(items, feature_id)["feature"]
        assert entry.get("source_refs")
        assert not entry.get("test_refs"), "Do not imply specific regression coverage"
    # Generic Help is no longer a fallback for curated capabilities.
    assert all(entry["help"] != "/help" for entry in items)
    help_html = (ROOT / "gui/templates/help.html").read_text(encoding="utf-8")
    for entry in items:
        if entry["help"].startswith("/help#"):
            assert f'id="{entry["help"].split("#", 1)[1]}"' in help_html
    for feature_id in ("capture-search", "capture-review", "wiki", "wiki-source-navigation", "trace-runtime"):
        feature = feature_detail(items, feature_id)["feature"]
        assert feature.get("source_refs"), feature_id
        assert feature["validation"] == "unverified"
    assert "test_fixtures/test_feature_trace_wiki_section_dossier.py" in feature_detail(
        items, "wiki-source-navigation")["feature"]["test_refs"]
    assert not feature_detail(items, "capture-search")["feature"].get("test_refs")
    for feature_id in ("research", "lua-converter", "sql-converter"):
        feature = feature_detail(items, feature_id)["feature"]
        assert feature.get("source_refs") and feature.get("test_refs"), feature_id
        assert feature["validation"] == "unverified"
    for feature_id in ("id-drift", "research-contradictions", "research-evidence",
                       "package-review", "package-scope", "package-create", "bindings"):
        feature = feature_detail(items, feature_id)["feature"]
        assert feature.get("source_refs"), feature_id
        assert not feature.get("test_refs"), feature_id
    expected_guidance = {
        "feature-trace": "Branch search",
        "live-client": "position sampling",
        "wiki": "sync/health",
        "zone-editor": "data source",
        "lua-converter": "ID-table",
        "sql-converter": "collision",
    }
    for feature_id, detail_term in expected_guidance.items():
        assert detail_term in feature_detail(items, feature_id)["feature"]["how_to_use"]
    for capability, expected in {
        "capture-search": "opcode",
        "capture-review": "Save what I typed",
        "research": "research session",
        "id-drift": "crosswalk",
        "package-review": "decision ledger",
        "package-create": "missing and skipped artifacts",
    }.items():
        assert expected in feature_detail(items, capability)["feature"]["how_to_use"]
    # Subfunction operator guidance must cover inputs, review/interpretation and bounds.
    reviewed = {
        "live-bridge": "credential configuration",
        "live-entity-stream": "ambiguous identities",
        "live-movement": "stop/disarm",
        "live-3d": "coordinate alignment",
        "wiki-cache": "missing-page diagnostics",
        "wiki-bulk": "bounded batch",
        "wiki-translation": "uncertain terms",
        "capture-query": "capture IDs",
        "capture-formats": "required metadata",
        "capture-paths": "coordinate provenance",
        "capture-import": "parser diagnostics",
        "capture-all-paths": "coordinate frame",
        "capture-bulk-ingest": "skipped/failed",
        "capture-metadata-import": "join keys",
        "capture-zone-review": "unresolved entity",
        "retail-versions-browse": "manifest",
        "retail-download-plan": "overwrite/hash",
        "retail-artifacts": "signature",
        "retail-compare": "file identities",
        "testing-scenario-builder": "test plan JSON",
        "testing-run-inspector": "missing observation",
        "testing-supervisor": "raw evidence",
    }
    assert len(reviewed) == 22
    for feature_id, keyword in reviewed.items():
        entry = feature_detail(items, feature_id)["feature"]
        assert entry.get("parent_id") and keyword in entry["how_to_use"], feature_id
        assert entry["validation"] != "tested"
    # Remaining priority subfunctions must give a concrete review action and evidence boundary.
    reviewed_subfunctions = {
        "ah-browse": "historical context",
        "ah-economy": "underlying transactions",
        "ah-item-picker": "exact item ID",
        "ah-preferences": "export CSV",
        "ah-restock": "guarded confirmation",
        "ah-recovery": "delivery attempts",
        "ah-scheduled-rewards": "queued reward",
        "ah-augmented-rewards": "augment parameters",
        "trace-evidence": "provider branches",
        "trace-runtime": "unresolved branches",
        "trace-wiki-provenance": "section locator",
        "ki-lua": "guard context",
        "ki-mapping-comparison": "Active DSP",
        "ki-operation-dependencies": "call site",
        "ki-evidence-handoff": "originating IDs",
        "validation-run-history": "case ID",
        "validation-live-target": "prerequisites",
    }
    assert len(reviewed_subfunctions) == 17
    for feature_id, expected in reviewed_subfunctions.items():
        entry = feature_detail(items, feature_id)["feature"]
        assert entry.get("parent_id") and expected in entry["how_to_use"], feature_id
        assert entry["validation"] != "tested"
    assert feature_detail(items, "missing-capability") is None
    assert "auction-house" in {f["id"] for f in search_catalog(items, "guarded")}
    assert all(f["module"] == "Research & Evidence" for f in search_catalog(items, module="Research & Evidence"))
    audit = audit_catalog()
    assert audit["feature_count"] == len(items)
    assert audit["module_count"] == len({f["module"] for f in items})
    assert audit["subfeature_count"] == sum(bool(f.get("parent_id")) for f in items)
    assert sum(audit["status_totals"]["implementation"].values()) == len(items)
    assert sum(audit["status_totals"]["validation"].values()) == len(items)
    assert audit["missing_operator_detail"] == {}, audit["missing_operator_detail"]
    assert audit["status_totals"]["validation"]["tested"] == sum(f["validation"] == "tested" for f in items)
    help_cov = audit["help_coverage"]
    assert sum(help_cov["counts"].values()) == len(items)
    assert set(help_cov["contextual"]) == {f["id"] for f in items if f["help"].startswith("/help#")}
    assert set(help_cov["generic"]) == {f["id"] for f in items if f["help"] == "/help"}
    assert set(help_cov["module_specific"]) == {f["id"] for f in items if not f["help"].startswith("/help")}
    assert all(f_id in help_cov["generic"] for ids in help_cov["generic_by_module"].values() for f_id in ids)
    quality = audit["quality_by_module"]
    assert sum(row["entries"] for row in quality.values()) == len(items)
    assert sum(row["source_refs"] for row in quality.values()) == sum(bool(f.get("source_refs")) for f in items)
    assert sum(row["test_refs"] for row in quality.values()) == sum(bool(f.get("test_refs")) for f in items)
    assert set(audit["provenance_gaps"]) == {
        f["id"] for f in items if not f.get("source_refs") or not f.get("test_refs")
    }
    documentation = audit["documentation_audit"]
    assert documentation["stage"] == "source_review"
    assert documentation["features_checked"] == len(items)
    assert documentation["finding_count"] == len(documentation["findings"])
    assert documentation["review_case_count"] == 9
    assert documentation["review_case_missing_markers"] == []
    assert all(case["status"] == "handler_source_verified_runtime_unverified" for case in documentation["review_cases"])
    assert all(case["handler_marker_present"] for case in documentation["review_cases"])
    assert all(case["contract_source_present"] for case in documentation["review_cases"])
    assert documentation["documentation_discrepancy_count"] == 0, documentation["review_cases"]
    assert {"guarded_execution_enqueue", "guarded_package_materialization"} <= {case["contract"]["boundary"] for case in documentation["review_cases"]}
    assert all(not case["documentation_discrepancies"] for case in documentation["review_cases"])
    assert {case["contract"]["boundary"] for case in documentation["review_cases"]} == {"read_only_review", "read_only_history", "design_only", "conversion_preview", "conversion_with_index_reads", "guarded_execution_enqueue", "guarded_package_materialization"}

    assert documentation["control_candidate_count"] == len(documentation["control_candidates"])
    assert documentation["finding_count"] > 0  # Unmapped provenance remains explicit.
    assert all(f["feature_id"] in {row["id"] for row in items} for f in documentation["findings"])
    assert all(c["classification"] == "needs_review" for c in documentation["control_candidates"])
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
    assert "Documentation accuracy triage" in page
    assert "Catalog depth:" in page
    assert "Help depth:" in page
    assert ("Prioritize generic Help links by module" in page) == bool(audit["help_coverage"]["generic_by_module"])
    assert "unverified" in page
    assert "uncataloged active pages" in page
    assert "Feature Trace" in page
    assert "Feature Catalog" in page
    detail_page = render("feature_catalog.html", "/feature-catalog",
                         features=items, modules=sorted({f["module"] for f in items}),
                         q="", module="", coverage=audit, detail=details, gui_audit=gui_audit, gui_inventory=inventory)
    assert "GUI control coverage audit" in detail_page
    assert "Automatic GUI control candidates" in detail_page
    assert "Documented subfunctions" in detail_page
    assert "Operator workflow" in detail_page
    assert "No implementation file or automated regression reference" in detail_page  # Explicit missing evidence
    trace_page = render("feature_catalog.html", "/feature-catalog", features=items,
                        modules=sorted({f["module"] for f in items}), q="", module="",
                        coverage=audit, detail=feature_detail(items, "trace-evidence"))
    assert "Implementation and test evidence" in trace_page
    assert "test_feature_trace_wiki_dossier.py" in trace_page
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
