#!/usr/bin/env python3
"""Regression coverage for the shared GUI application shell."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import escape

from test_gui_information_architecture import main as validate_route_map
from workbench.gui_shell import WORKSPACES, build_shell_context, route_owner


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "gui" / "templates"


def request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path), method="GET")


def context_for(path: str, settings=None) -> dict:
    return build_shell_context(
        path=path,
        method="GET",
        settings=settings or {},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def render(name: str, path: str, **values) -> str:
    brand = values.pop("_brand", {
        "enabled": True,
        "text": "ValhallaXI",
        "icon": "/static/valhalla_logo.png",
    })
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(("html",)),
    )
    brand_settings = {
        "shell_brand_enabled": "1" if brand.get("enabled") else "0",
        "shell_brand_text": brand.get("text", ""),
        "shell_brand_icon": brand.get("icon", ""),
    }
    env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        shell_context=lambda _request: context_for(path, settings=brand_settings),
    )
    return env.get_template(name).render(request=request(path), **values)


def main():
    assert validate_route_map() == 0

    names = [workspace["name"] for workspace in WORKSPACES]
    assert names == [
        "Home / Project",
        "Features",
        "Domains",
        "Backport & Migration",
        "Captures",
        "Server",
        "Client",
        "Validation",
        "Packages",
        "Tools",
        "Settings",
    ]
    assert route_owner("/captures/42/timeline")["home"] == "Captures"
    assert route_owner("/ocr")["home"] == "Captures"
    assert route_owner("/ocr")["section"] == "YouTube OCR"
    assert route_owner("/ocr/example-run")["home"] == "Captures"
    assert route_owner("/ocr/example-run")["section"] == "YouTube OCR"
    assert route_owner("/entity")["home"] == "Server"
    assert route_owner("/zoneplot/restore", "POST")["section"] == "Editors > Zone Editor"
    assert route_owner("/zoneplot2")["section"] == "Editors > Zone Editor"
    assert route_owner("/itemedit/123.json")["section"] == "Editors > Item Editor"
    assert route_owner("/features/trace")["home"] == "Features"
    assert route_owner("/features/trace")["section"] == "Feature Trace"
    assert route_owner("/features/check")["section"] == "Feature Checker"
    assert route_owner("/validation")["home"] == "Validation"
    assert route_owner("/validation/runs")["section"] == "Runs & Results"
    assert route_owner("/validation/runs/example-run")["section"] == "Runs & Results"
    assert route_owner("/validation/live-target")["section"] == "Live Target"
    assert route_owner("/validation/live-target", "POST")["section"] == "Live Target"
    assert route_owner("/packages")["home"] == "Packages"
    assert route_owner("/packages")["section"] == "Package Library"
    assert route_owner("/packages/review")["section"] == "Review & Readiness"
    assert route_owner("/packages/create")["section"] == "Create Package"
    assert route_owner("/packages/create", "POST")["section"] == "Create Package"
    assert route_owner("/packages/scope")["section"] == "Scope Review"
    assert route_owner("/packages/scope/decision", "POST")["section"] == "Scope Review"
    assert route_owner("/packages/scope/review", "POST")["section"] == "Scope Review"
    assert route_owner("/domains/assault")["home"] == "Domains"
    assert route_owner("/domains/assault")["section"] == "Battle Systems > Assault"
    assert route_owner("/nyzul")["home"] == "Domains"
    assert route_owner("/nyzul/data.json")["section"] == "Battle Systems > Nyzul Isle"

    planned = build_shell_context(
        path="/", method="GET", settings={}, workspace_slug="validation",
        default_topaz_root="C:/missing-topaz", default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )
    assert planned["active_home"] == "Validation"
    packages_workspace = next(workspace for workspace in WORKSPACES if workspace["name"] == "Packages")
    assert packages_workspace["href"] == "/packages"
    assert next(section for section in packages_workspace["sections"] if section["label"] == "Package Library")["href"] == "/packages"
    assert next(section for section in packages_workspace["sections"] if section["label"] == "Scope Review")["href"] == "/packages/scope"
    assert next(section for section in packages_workspace["sections"] if section["label"] == "Create Package")["href"] == "/packages/create"
    assert next(section for section in packages_workspace["sections"] if section["label"] == "Review & Readiness")["href"] == "/packages/review"
    validation_workspace = next(workspace for workspace in WORKSPACES if workspace["name"] == "Validation")
    assert validation_workspace["href"] == "/validation"
    assert next(section for section in validation_workspace["sections"] if section["label"] == "Dashboard")["href"] == "/validation"
    assert next(section for section in validation_workspace["sections"] if section["label"] == "Runs & Results")["href"] == "/validation/runs"
    assert next(section for section in validation_workspace["sections"] if section["label"] == "Live Target")["href"] == "/validation/live-target"

    ocr = context_for("/ocr")
    assert ocr["active_home"] == "Captures"
    assert next(section for section in ocr["sections"] if section["active"])["label"] == "YouTube OCR"
    ocr_run = context_for("/ocr/example-run")
    assert ocr_run["active_home"] == "Captures"
    assert next(section for section in ocr_run["sections"] if section["active"])["label"] == "YouTube OCR"

    captures = next(workspace for workspace in WORKSPACES if workspace["name"] == "Captures")
    assert next(section for section in captures["sections"] if section["href"] == "/captures/search")["label"] == "Evidence Search"
    assert next(section for section in captures["sections"] if section["href"] == "/captures/query")["label"] == "Data Explorer"
    assert {section["label"] for section in captures["sections"]}.isdisjoint({"Path Plot", "All Paths"})

    viewer = context_for("/zones/42/view3d_all")
    assert viewer["active_home"] == "Server"
    assert next(section for section in viewer["sections"] if section["active"])["label"] == "3D Viewer"

    tools = build_shell_context(
        path="/entity", method="GET", settings={}, shell_override="tools",
        default_topaz_root="C:/missing-topaz", default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )
    assert tools["active_home"] == "Tools"
    assert next(section for section in tools["sections"] if section["active"])["label"] == "Lookup & Decode: Entity"
    tools_workspace = next(workspace for workspace in WORKSPACES if workspace["name"] == "Tools")
    assert next(section for section in tools_workspace["sections"] if section["label"] == "Lookup & Decode: Entity")["href"] == "/entity?shell=tools"

    domains = next(workspace for workspace in WORKSPACES if workspace["name"] == "Domains")
    top_labels = {section["label"] for section in domains["sections"]}
    assert top_labels >= {
        "Abyssea", "Battlefields", "Battle Systems", "Conflict / Battle", "Combat",
        "Dynamis", "Escha", "Hobbies", "HELM", "Events", "Missions", "Quests",
        "Records of Eminence", "Trust", "Other",
    }
    assert not any(section["label"].startswith("↳") for section in domains["sections"])

    battle_systems = next(section for section in domains["sections"] if section["label"] == "Battle Systems")
    assert next(child for child in battle_systems["children"] if child["label"] == "Assault")["href"] == "/domains/assault"
    assert next(child for child in battle_systems["children"] if child["label"] == "Nyzul Isle")["href"] == "/nyzul"

    abyssea = next(section for section in domains["sections"] if section["label"] == "Abyssea")
    assert {child["label"] for child in abyssea["children"]} == {
        "Altepa", "Attohwa", "Grauberg", "Konschtat", "La Theine", "Misareaux",
        "Tahrongi", "Uleguerand", "Vunkerl", "Bastion",
    }
    battlefields = next(section for section in domains["sections"] if section["label"] == "Battlefields")
    assert {child["label"] for child in battlefields["children"]} >= {
        "AMAN-Trove", "Ambuscade", "ANNM", "BCNM", "ENM", "HKCNM", "ISNM",
        "KCNM", "KSNM", "Login", "Master Trials", "SCNM", "SKCNM", "Walk of Echoes",
    }

    nyzul = context_for("/nyzul")
    assert nyzul["active_home"] == "Domains"
    active_group = next(section for section in nyzul["sections"] if section["active"])
    assert active_group["label"] == "Battle Systems"
    assert next(child for child in active_group["children"] if child["active"])["label"] == "Nyzul Isle"

    configured = build_shell_context(
        path="/captures",
        method="GET",
        settings={
            "backport_root": "D:/work/backport-project",
            "topaz_server_path": "D:/servers/topaz",
            "dsp_server_path": "D:/servers/dsp",
            "ffxi_install_path": "D:/games/FFXI",
        },
        default_topaz_root="C:/topaz",
        default_backport_root="C:/workspace",
        path_exists=lambda _path: True,
    )
    values = {item["label"]: item["value"] for item in configured["snapshot_context"]}
    assert values == {
        "Project": "backport-project",
        "Source snapshot": "UNKNOWN",
        "Target snapshot": "UNKNOWN",
        "Client build": "UNKNOWN",
    }

    pages = (
        ("help.html", "/help", {}),
        ("captures.html", "/captures", {
            "q": "", "missions": [], "content_types": [], "content_type": "",
            "all_tags": [], "tag": "", "rows": [],
        }),
        ("itemedit.html", "/itemedit", {}),
        ("feature_trace.html", "/features/trace", {"q": "", "depth": 3, "direction": "both", "result": None, "matches": [], "error": None}),
        ("feature_checker.html", "/features/check", {"q": "", "result": None, "matches": [], "error": None}),
        ("validation_dashboard.html", "/validation", {"runs": [], "status_counts": {}, "result_counts": {}, "total_results": 0, "error": None}),
        ("validation_runs.html", "/validation/runs", {"q": "", "status": "", "statuses": [], "runs": [], "error": None}),
        ("validation_run_detail.html", "/validation/runs/test", {"run": None, "results": [], "error": None, "run_id": "test"}),
        ("validation_live_target.html", "/validation/live-target", {"form": {"target_family": "DSP", "target_root": "", "backend": "sqlite", "sqlite_db": "", "host": "127.0.0.1", "port": "3306", "user": "", "database": "", "password_env": "FFXI_DB_PASSWORD", "target_snapshot_id": "", "source_snapshot_id": "", "feature_id": "", "run_id": "", "persist": False, "expected_json": "{}"}, "result": None, "error": None}),
        ("packages_library.html", "/packages", {"q": "", "project_root": "C:/workspace", "packages": []}),
        ("packages_scope.html", "/packages/scope", {"migrations": [], "migration_id": "", "q": "", "decision": "", "depth": 6, "scope": None, "error": None}),
        ("packages_review.html", "/packages/review", {"packages": [], "package": "", "target_root": "", "review": None, "manifest": {}, "validation": {}, "error": None}),
        ("packages_create.html", "/packages/create", {"migrations": [], "form": {"migration_id": "", "source_root": "", "source_family": "LSB", "target_family": "DSP", "package_path": "packages/"}, "result": None, "error": None}),
    )
    for template, path, values in pages:
        html = render(template, path, **values)
        for workspace in WORKSPACES:
            assert str(escape(workspace["name"])) in html, (template, workspace["name"])
        assert "Source snapshot" in html
        assert "Not configured" in html
        assert 'aria-label="Primary workspaces"' in html

    default_brand_html = render("help.html", "/help")
    assert "/static/valhalla_logo.png" in default_brand_html
    assert ">ValhallaXI</span>" in default_brand_html

    custom_brand_html = render(
        "help.html", "/help",
        _brand={"enabled": True, "text": "My Server", "icon": "/static/branding/custom_brand.png"},
    )
    assert "/static/branding/custom_brand.png" in custom_brand_html
    assert ">My Server</span>" in custom_brand_html
    assert ">ValhallaXI</span>" not in custom_brand_html

    hidden_brand_html = render(
        "help.html", "/help",
        _brand={"enabled": False, "text": "Hidden Brand", "icon": "/static/branding/custom_brand.png"},
    )
    assert "Hidden Brand" not in hidden_brand_html
    assert 'class="shell-brand"' not in hidden_brand_html

    settings_source=(TEMPLATES/"settings.html").read_text(encoding="utf-8")
    assert 'name="shell_brand_enabled"' in settings_source
    assert 'name="shell_brand_text"' in settings_source
    assert 'name="shell_brand_icon_upload"' in settings_source
    assert 'name="shell_brand_reset_icon"' in settings_source
    assert 'enctype="multipart/form-data"' in settings_source

    captures_html = render(
        "captures.html", "/captures", q="", missions=[], content_types=[],
        content_type="", all_tags=[], tag="", rows=[],
    )
    capture_template_contracts = {
        "capture_detail.html": ["{% block shell_mode %}dense{% endblock %}", "capture-stats", "capture-meta", "capture-actions", "Capture integrity", "capture-npc-filter", "capture-npc-table"],
        "capture_timeline.html": ["{% block shell_mode %}dense{% endblock %}", "capture-timeline-page", "position:sticky", "Packet Browser"],
        "capture_packets.html": ["{% block shell_mode %}dense{% endblock %}", "capture-packets-page", "decoded field"],
        "capture_packet_detail.html": ["{% block shell_mode %}dense{% endblock %}", "capture-packet-page", "Session packets", "Source provenance"],
        "capture_search.html": ["{% block shell_mode %}dense{% endblock %}", "capture-search-page", "Evidence Search"],
        "capture_add.html": ["{% block shell_mode %}dense{% endblock %}", "capture-upload-grid", "Formats / guidance"],
        "capture_new.html": ["{% block shell_mode %}dense{% endblock %}", "capture-new-form"],
        "capture_alignment.html": ["{% block shell_mode %}dense{% endblock %}", "align-section", "Alignment candidates"],
        "capture_query.html": ["{% block shell_mode %}dense{% endblock %}", "capture-query-page"],
        "capture_source_locator.html": ["{% block shell_mode %}dense{% endblock %}", "capture-source-page"],
        "capture_delete_confirm.html": ["{% block shell_mode %}dense{% endblock %}", "capture-delete-page"],
        "capture_help.html": ["capture-help-section", "Capture Ingestion Help"],
        "path_plot.html": ["{% block shell_mode %}dense{% endblock %}", "capture-path-page", "width:min(100%,1100px)", "All paths"],
        "path_plot_all.html": ["{% block shell_mode %}dense{% endblock %}", "capture-all-paths-page", "width:min(100%,1200px)", "Capture entities"],
    }
    capture_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(("html",)))
    capture_wrapper_source=(TEMPLATES/"workbench_page.html").read_text(encoding="utf-8")
    for template_name, markers in capture_template_contracts.items():
        capture_env.get_template(template_name)
        source=(TEMPLATES/template_name).read_text(encoding="utf-8")
        for marker in markers:
            if marker == "{% block shell_mode %}dense{% endblock %}" and '{% extends "workbench_page.html" %}' in source:
                assert marker in capture_wrapper_source,(template_name,"wrapper must preserve dense shell mode")
            else:
                assert marker in source,(template_name,marker)
    library_search_contracts = {
        "itembrowser.html": ["Item Browser", "ib-page"],
        "keyitems.html": ["{% block shell_mode %}dense{% endblock %}", "keyitems-page"],
        "dialog.html": ["{% block shell_mode %}dense{% endblock %}", "dialog-browser-page", "Dialog Drift Overview"],
        "dialog_drift.html": ["{% block shell_mode %}dense{% endblock %}", "dialog-drift-page", "Dialog Browser"],
        "sql.html": ["{% block shell_mode %}dense{% endblock %}", "sql-browser-page", "Entity Lookup"],
        "zones_browse.html": ["{% block shell_mode %}dense{% endblock %}", "zones-browser-page"],
        "missions.html": ["{% block shell_mode %}dense{% endblock %}", "missions-browser-page", "mission-card"],
        "backport_bindings.html": ["{% block shell_mode %}dense{% endblock %}", "binding-reference-page"],
        "gaps.html": ["{% block shell_mode %}dense{% endblock %}", "entity-gaps-page"],
        "domains_index.html": ["{% block shell_mode %}dense{% endblock %}", "domains-index-page"],
        "feature_checker.html": ["{% block shell_mode %}dense{% endblock %}", "feature-checker-page", "Feature Trace"],
        "research_sessions.html": ["{% block shell_mode %}dense{% endblock %}", "research-sessions-page", 'href="/researchgaps"'],
        "research_contradictions.html": ["{% block shell_mode %}dense{% endblock %}", "research-contradictions-page", 'href="/researchgaps"'],
        "research_evidence.html": ["{% block shell_mode %}dense{% endblock %}", "research-evidence-page"],
        "research_gaps.html": ["{% block shell_mode %}dense{% endblock %}", "research-gaps-page"],
    }
    wrapper_source=(TEMPLATES/"workbench_page.html").read_text(encoding="utf-8")
    for template_name, markers in library_search_contracts.items():
        capture_env.get_template(template_name)
        source=(TEMPLATES/template_name).read_text(encoding="utf-8")
        assert 'href="/research/gaps"' not in source,(template_name,"stale Research Gaps route")
        for marker in markers:
            if marker == "{% block shell_mode %}dense{% endblock %}" and '{% extends "workbench_page.html" %}' in source:
                assert marker in wrapper_source,(template_name,"wrapper must preserve dense shell mode")
            else:
                assert marker in source,(template_name,marker)

    workflow_ux_contracts = {
        "wiki.html": ["{% block shell_mode %}dense{% endblock %}", "wiki-compiler-page", "wiki-actions", "wiki-kpis", "Evidence mapping ledger", "Dual-wiki claim comparison"],
        "research_session_detail.html": ["{% block shell_mode %}dense{% endblock %}", "research-session-page", "research-meta", "research-run-grid", "Typed Tool Transcript", "Research Proposals", "Final Report"],
    }
    for template_name, markers in workflow_ux_contracts.items():
        capture_env.get_template(template_name)
        source=(TEMPLATES/template_name).read_text(encoding="utf-8")
        for marker in markers:
            if marker == "{% block shell_mode %}dense{% endblock %}" and '{% extends "workbench_page.html" %}' in source:
                assert marker in wrapper_source,(template_name,"wrapper must preserve dense shell mode")
            else:
                assert marker in source,(template_name,marker)

    client_overview_contracts = [
        "{% block shell_mode %}dense{% endblock %}",
        "client-overview-page",
        "client-kpis",
        "client-form-grid",
        "Compare Client Builds",
        "ENTITY / Actor Identity Coverage",
        "EVENT Identity Results",
    ]
    client_overview_source=(TEMPLATES/"client_overview.html").read_text(encoding="utf-8")
    client_overview_wrapper=(TEMPLATES/"workbench_page.html").read_text(encoding="utf-8")
    capture_env.get_template("client_overview.html")
    for marker in client_overview_contracts:
        if marker == "{% block shell_mode %}dense{% endblock %}" and '{% extends "workbench_page.html" %}' in client_overview_source:
            assert marker in client_overview_wrapper,"wrapper must preserve dense shell mode"
        else:
            assert marker in client_overview_source,marker

    package_workflow_contracts = {
        "packages_scope.html": ["{% block shell_mode %}dense{% endblock %}", "package-scope-page", "Package Workflow", "1 · Scope", "scope-decision-form"],
        "packages_create.html": ["{% block shell_mode %}dense{% endblock %}", "package-create-page", "2 · Create", "package-form-grid"],
        "packages_review.html": ["{% block shell_mode %}dense{% endblock %}", "package-review-page", "3 · Review", "package-review-section"],
    }
    for template_name, markers in package_workflow_contracts.items():
        capture_env.get_template(template_name)
        source=(TEMPLATES/template_name).read_text(encoding="utf-8")
        for marker in markers:
            if marker == "{% block shell_mode %}dense{% endblock %}" and '{% extends "workbench_page.html" %}' in source:
                assert marker in wrapper_source,(template_name,"wrapper must preserve dense shell mode")
            else:
                assert marker in source,(template_name,marker)

    assert '<body class="shell-dense">' in captures_html
    assert 'class="wb-page-title">Captures</span>' in captures_html
    assert 'form class="search wb-filter-row"' in captures_html
    assert re.search(r'class="workspace-link active"\s+href="/captures"', captures_html)
    assert 'href="/captures/plot"' not in captures_html
    assert 'href="/captures/plot_all"' not in captures_html

    data_explorer_html = render(
        "capture_query.html", "/captures/query",
        table="capture_raw_packets",
        dataset={
            "label": "Raw packets",
            "description": "Canonical raw packet bytes with source provenance.",
        },
        dataset_groups=[
            {
                "label": "Protocol & Raw Evidence",
                "datasets": [
                    {
                        "table": "capture_raw_packets",
                        "label": "Raw packets",
                        "description": "Canonical raw packet bytes.",
                    },
                ],
            },
            {
                "label": "Battle & Actions",
                "datasets": [
                    {
                        "table": "capture_actions",
                        "label": "Battle actions",
                        "description": "Canonical action observations.",
                    },
                ],
            },
        ],
        capture_id="", q="",
        cols=["capture_id", "seq", "ts", "direction", "opcode", "raw_hex", "source_file"],
        display_cols=["capture_id", "seq", "ts", "direction", "opcode", "source_file"],
        rows=[{
            "capture_id": 7,
            "seq": 42,
            "ts": "2026-09-30T12:00:00",
            "direction": "incoming",
            "opcode": "0x037",
            "raw_hex": "37304E00",
            "source_file": "incoming/0x037.log",
        }],
        page=1, total=1, total_pages=1,
    )
    assert "Capture Data Explorer" in data_explorer_html
    assert "Evidence Search" in data_explorer_html
    assert "Protocol &amp; Raw Evidence" in data_explorer_html
    assert "Battle &amp; Actions" in data_explorer_html
    assert "Raw row / provenance" in data_explorer_html
    assert "7 columns" in data_explorer_html
    assert "/captures/7/packets/42" in data_explorer_html

    evidence_search_html = render(
        "capture_search.html", "/captures/search",
        module="vendors",
        module_meta={
            "label": "Vendors & Shops",
            "description": "ShopStock, GuildStock and price observations across captures.",
            "hint": "Vendor/NPC name, item name, or exact item/entity ID",
        },
        modules=[
            {"id": "events", "label": "Events & Dialogue", "description": "CSIDs and dialogue."},
            {"id": "packets", "label": "Raw Protocol", "description": "Canonical raw packets."},
            {"id": "entities", "label": "Entities", "description": "NPC/mob identity."},
            {"id": "battle", "label": "Battle & Actions", "description": "Actions and HP."},
            {"id": "items", "label": "Items & Key Items", "description": "Item evidence."},
            {"id": "vendors", "label": "Vendors & Shops", "description": "Shop evidence."},
            {"id": "crafting", "label": "Crafting", "description": "Craft evidence."},
            {"id": "chat", "label": "Chat & Text", "description": "Chat evidence."},
            {"id": "spatial", "label": "Spatial & Movement", "description": "Spatial evidence."},
            {"id": "environment", "label": "Environment & World State", "description": "World-state evidence."},
        ],
        q="Potion", entity="", message_id="", ev_opcodes=[], available_ev_opcodes=[],
        pk_category="", pk_opcode="", categories=[],
        events=[], packets=[],
        generic_rows=[{
            "capture_id": 9,
            "capture_label": "vendor sample",
            "evidence_kind": "VENDOR",
            "zone": "Port Bastok",
            "ts": "2026-09-30T12:00:00",
            "subject_id": 123,
            "title": "Vendor NPC",
            "summary": "shopstock_buy_db • Potion • price=100",
            "dataset": "capture_structured_records",
            "record_id": "shop.db:shopstock_buy_db:1",
        }],
        page=1, total=1, total_pages=1, qs_pairs=[("module", "vendors"), ("q", "Potion")],
    )
    assert "Evidence Search" in evidence_search_html
    assert "Vendors &amp; Shops" in evidence_search_html
    assert "Battle &amp; Actions" in evidence_search_html
    assert "Crafting" in evidence_search_html
    assert "Spatial &amp; Movement" in evidence_search_html
    assert "Environment &amp; World State" in evidence_search_html
    assert "shopstock_buy_db" in evidence_search_html
    assert "capture_structured_records" in evidence_search_html
    assert "/captures/9/timeline" in evidence_search_html
    capture_detail_template = (TEMPLATES / "capture_detail.html").read_text(encoding="utf-8")
    # Path plotting now opens the Zone Editor Paths tab; the legacy 2D overlay stays as a secondary link.
    assert "/zoneplot/from_capture?capture_id={{ detail.capture_id }}" in capture_detail_template
    assert "/captures/plot_all?capture_id={{ detail.capture_id }}" in capture_detail_template

    domains_html = render("domain_assault.html", "/domains/assault")
    assert 'class="shell-menu section-menu"' in domains_html
    assert '<div class="shell-group-title">Battle Systems</div>' in domains_html
    assert re.search(r'class="section-link active"\s+href="/domains/assault" aria-current="page">Assault</a>', domains_html)
    assert "↳ Assault" not in domains_html

    model_html = render("model_viewer.html", "/modelviewer")
    assert 'aria-label="Primary workspaces"' in model_html
    assert re.search(r'class="workspace-link active"\s+href="/modelviewer"', model_html)

    assert '<body class="shell-dense">' in model_html
    assert 'class="dense-panel"' in model_html
    assert 'class="wb-page-title">Model Viewer</span>' in model_html

    capture_env.get_template("zone_view3d.html")
    capture_env.get_template("packets_decode.html")
    zone_view3d_template=(TEMPLATES/"zone_view3d.html").read_text(encoding="utf-8")
    assert '{% extends "workbench_page.html" %}' in zone_view3d_template
    assert "{% block page_class %}zone-view3d-page{% endblock %}" in zone_view3d_template
    assert "{% block page_heading %}3D Zone Viewer{% endblock %}" in zone_view3d_template
    assert 'href="/zoneplot2?zone={{ zoneid }}"' in zone_view3d_template
    assert "calc(100vh - var(--shell-h)" in zone_view3d_template

    # Compact shell v2 stays one persistent global row and moves secondary state into popovers.
    assert 'id="app-shell"' in model_html
    assert 'class="shellbar"' in model_html
    assert 'class="shell-menu section-menu"' in model_html
    assert 'class="shell-menu context-menu"' in model_html
    assert 'class="context-list"' in model_html
    assert 'class="navrow contextbar"' not in model_html
    assert 'class="navrow workspace-nav"' not in model_html
    assert 'class="navrow section-nav"' not in model_html

    zone2_html = render("zone_plot2.html", "/zoneplot2")
    assert '<body class="shell-dense">' in zone2_html
    assert 'id="app-shell"' in zone2_html
    assert 'id="zbar" class="dense-toolbar"' in zone2_html
    assert 'class="zpanel dense-panel"' in zone2_html
    assert 'class="ztabs dense-tabs"' in zone2_html
    assert 'id="helpdrawer" class="dense-drawer"' in zone2_html
    assert 'body>header{display:none}' not in zone2_html
    assert 'zp2-menu' not in zone2_html
    assert 'id="zmenuBtn"' not in zone2_html

    validation_html = render("validation_dashboard.html", "/validation", runs=[], status_counts={}, result_counts={}, total_results=0, error=None)
    assert '<body class="shell-dense">' in validation_html
    assert 'class="wb-page-title">Validation</span>' in validation_html
    assert 'class="wb-readonly-badge">Read only</span>' in validation_html

    validation_runs_html = render("validation_runs.html", "/validation/runs", q="", status="", statuses=[], runs=[], error=None)
    assert '<body class="shell-dense">' in validation_runs_html
    assert 'wb-archetype-browser' in validation_runs_html
    assert 'form class="search wb-filter-row"' in validation_runs_html
    assert 'class="wb-readonly-badge">Read only</span>' in validation_runs_html

    packages_html = render("packages_library.html", "/packages", q="", project_root="C:/workspace", packages=[])
    assert '<body class="shell-dense">' in packages_html
    assert 'wb-archetype-browser' in packages_html
    assert 'class="wb-page-title">Package Library</span>' in packages_html
    assert 'form class="search wb-filter-row"' in packages_html

    validation_shell = context_for("/validation")
    assert validation_shell["active_home"] == "Validation"
    assert next(section for section in validation_shell["sections"] if section["active"])["label"] == "Dashboard"
    validation_runs_shell = context_for("/validation/runs/test-run")
    assert validation_runs_shell["active_home"] == "Validation"
    assert next(section for section in validation_runs_shell["sections"] if section["active"])["label"] == "Runs & Results"
    live_target_shell = context_for("/validation/live-target")
    assert live_target_shell["active_home"] == "Validation"
    assert next(section for section in live_target_shell["sections"] if section["active"])["label"] == "Live Target"

    packages_shell = context_for("/packages")
    assert packages_shell["active_home"] == "Packages"
    assert next(section for section in packages_shell["sections"] if section["active"])["label"] == "Package Library"
    package_scope_shell = context_for("/packages/scope")
    assert package_scope_shell["active_home"] == "Packages"
    assert next(section for section in package_scope_shell["sections"] if section["active"])["label"] == "Scope Review"
    package_review_shell = context_for("/packages/review")
    assert package_review_shell["active_home"] == "Packages"
    assert next(section for section in package_review_shell["sections"] if section["active"])["label"] == "Review & Readiness"
    package_create_shell = context_for("/packages/create")
    assert package_create_shell["active_home"] == "Packages"
    assert next(section for section in package_create_shell["sections"] if section["active"])["label"] == "Create Package"

    trace_html = render("feature_trace.html", "/features/trace", q="", depth=3, direction="both", result=None, matches=[], error=None)
    assert '<body class="shell-dense">' in trace_html
    assert 'id="featureTraceTop" class="search wb-filter-row"' in trace_html
    assert 'wb-archetype-workbench' in trace_html
    assert 'class="wb-page-title">Feature Trace</span>' in trace_html

    trace_shell = context_for("/features/trace")
    assert trace_shell["active_home"] == "Features"
    assert next(section for section in trace_shell["sections"] if section["active"])["label"] == "Feature Trace"
    checker_shell = context_for("/features/check")
    assert next(section for section in checker_shell["sections"] if section["active"])["label"] == "Feature Checker"

    entity_html = render("entity.html", "/entity", q="", matches=[], total=0, page=1, total_pages=1, zone_names={})
    assert '<body class="shell-dense">' in entity_html
    assert 'class="wb-page-title">Entity Lookup</span>' in entity_html
    assert 'form class="search wb-filter-row"' in entity_html

    events_html = render("events.html", "/events", zones=[], zone="", q="", rows=[], generated_note=None, health_summary={})
    assert '<body class="shell-dense">' in events_html
    assert 'wb-archetype-browser' in events_html
    assert 'class="wb-page-title">Events / CSID Browser</span>' in events_html
    assert 'form class="search wb-filter-row"' in events_html

    packets_html = render("packets.html", "/packets", q="", direction="s2c", opcodes=[])
    assert '<body class="shell-dense">' in packets_html
    assert 'class="wb-page-title">Packet Tools</span>' in packets_html
    assert 'Manual Packet Viewer / Decoder' in packets_html
    assert 'Browse known opcodes' in packets_html

    editor_html = render("itemedit.html", "/itemedit")
    assert editor_html.count("Editors: Zone Editor") == 1
    assert 'href="/zoneplot2"' in editor_html
    assert 'href="/zoneplot"' not in editor_html
    assert "Editors: Item Editor" in editor_html
    assert "Lookup &amp; Decode: Entity" in editor_html
    assert "section-link active mutation" in editor_html
    assert "Specialized: Nyzul" not in editor_html
    assert '<body class="shell-dense">' in editor_html
    assert 'id="itemEditorTop" class="dense-toolbar"' in editor_html
    assert '<div id="itemBatchEditor"' in editor_html
    assert 'id="itemSessionHistory" class="dense-toolbar"' in editor_html
    assert 'class="editor-toolbar dense-toolbar"' in editor_html
    assert any(
        section.get("href") == "/backport/package"
        for workspace in WORKSPACES
        for section in workspace["sections"]
    )

    print("Shared GUI shell regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
