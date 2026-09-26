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


def context_for(path: str) -> dict:
    return build_shell_context(
        path=path,
        method="GET",
        settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def render(name: str, path: str, **values) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(("html",)),
    )
    env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        shell_context=lambda _request: context_for(path),
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
    assert route_owner("/entity")["home"] == "Server"
    assert route_owner("/zoneplot/restore", "POST")["section"] == "Editors > Zone Editor"
    assert route_owner("/itemedit/123.json")["section"] == "Editors > Item Editor"
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
    assert any(workspace["href"] == "/?workspace=packages" for workspace in WORKSPACES)

    captures = next(workspace for workspace in WORKSPACES if workspace["name"] == "Captures")
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
    assert next(section for section in domains["sections"] if section["label"] == "↳ Assault")["href"] == "/domains/assault"
    assert next(section for section in domains["sections"] if section["label"] == "↳ Nyzul Isle")["href"] == "/nyzul"
    assert {section["label"] for section in domains["sections"] if section.get("planned")} >= {
        "Abyssea", "Battlefields", "↳ AMAN-Trove", "↳ Ambuscade", "↳ ANNM",
        "↳ BCNM", "↳ ENM", "↳ HKCNM", "↳ ISNM", "↳ KCNM", "↳ KSNM",
        "↳ Login", "↳ Master Trials", "↳ SCNM", "↳ SKCNM", "↳ Walk of Echoes",
        "Battle Systems", "Conflict / Battle", "Combat",
        "Dynamis", "Escha", "Hobbies", "HELM", "Events", "Missions", "Quests",
        "RoE", "Trust", "Other",
    }

    nyzul = context_for("/nyzul")
    assert nyzul["active_home"] == "Domains"
    assert next(section for section in nyzul["sections"] if section["active"])["label"] == "↳ Nyzul Isle"

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
    )
    for template, path, values in pages:
        html = render(template, path, **values)
        for workspace in WORKSPACES:
            assert str(escape(workspace["name"])) in html, (template, workspace["name"])
        assert "Source snapshot" in html
        assert "Not configured" in html
        assert 'aria-label="Primary workspaces"' in html

    captures_html = render(
        "captures.html", "/captures", q="", missions=[], content_types=[],
        content_type="", all_tags=[], tag="", rows=[],
    )
    assert re.search(r'class="workspace-link active"\s+href="/captures"', captures_html)
    assert 'href="/captures/plot"' not in captures_html
    assert 'href="/captures/plot_all"' not in captures_html
    capture_detail_template = (TEMPLATES / "capture_detail.html").read_text(encoding="utf-8")
    assert "/captures/plot?capture_id={{ detail.capture_id }}" in capture_detail_template
    assert "/captures/plot_all?capture_id={{ detail.capture_id }}" in capture_detail_template

    model_html = render("model_viewer.html", "/modelviewer")
    assert 'aria-label="Primary workspaces"' in model_html
    assert re.search(r'class="workspace-link active"\s+href="/modelviewer"', model_html)

    editor_html = render("itemedit.html", "/itemedit")
    assert "Editors: Zone Editor" in editor_html
    assert "Editors: Item Editor" in editor_html
    assert "Lookup &amp; Decode: Entity" in editor_html
    assert "section-link active mutation" in editor_html
    assert "Specialized: Nyzul" not in editor_html
    assert any(
        section.get("href") == "/backport/package"
        for workspace in WORKSPACES
        for section in workspace["sections"]
    )

    print("Shared GUI shell regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
