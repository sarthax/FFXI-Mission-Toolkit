"""Shared GUI shell navigation and configured-context presentation.

The shell is deliberately read-only. It consumes the approved route map and existing
settings; it does not select snapshots, mutate configuration, or invent source identity.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
ROUTE_MAP = ROOT / "docs" / "workbench" / "GUI_ROUTE_MAP.json"


WORKSPACES = (
    {
        "name": "Home / Project",
        "href": "/",
        "sections": (
            {"label": "Dashboard", "href": "/"},
            {"label": "Roadmap", "href": "/roadmap"},
            {"label": "Help", "href": "/help"},
        ),
    },
    {
        "name": "Features",
        "href": "/missions",
        "sections": (
            {"label": "Mission Explorer", "href": "/missions"},
            {"label": "Feature Trace", "href": "/features/trace"},
            {"label": "Feature Checker", "href": "/features/check"},
        ),
    },
    {
        "name": "Domains",
        "href": "/domains/assault",
        "sections": (
            {
                "label": "Abyssea",
                "planned": True,
                "children": (
                    {"label": "Altepa", "href": None, "planned": True},
                    {"label": "Attohwa", "href": None, "planned": True},
                    {"label": "Grauberg", "href": None, "planned": True},
                    {"label": "Konschtat", "href": None, "planned": True},
                    {"label": "La Theine", "href": None, "planned": True},
                    {"label": "Misareaux", "href": None, "planned": True},
                    {"label": "Tahrongi", "href": None, "planned": True},
                    {"label": "Uleguerand", "href": None, "planned": True},
                    {"label": "Vunkerl", "href": None, "planned": True},
                    {"label": "Bastion", "href": None, "planned": True},
                ),
            },
            {
                "label": "Battlefields",
                "planned": True,
                "children": (
                    {"label": "AMAN-Trove", "href": None, "planned": True},
                    {"label": "Ambuscade", "href": None, "planned": True},
                    {"label": "ANNM", "href": None, "planned": True},
                    {"label": "BCNM", "href": None, "planned": True},
                    {"label": "ENM", "href": None, "planned": True},
                    {"label": "HKCNM", "href": None, "planned": True},
                    {"label": "ISNM", "href": None, "planned": True},
                    {"label": "KCNM", "href": None, "planned": True},
                    {"label": "KSNM", "href": None, "planned": True},
                    {"label": "Login", "href": None, "planned": True},
                    {"label": "Master Trials", "href": None, "planned": True},
                    {"label": "SCNM", "href": None, "planned": True},
                    {"label": "SKCNM", "href": None, "planned": True},
                    {"label": "Walk of Echoes", "href": None, "planned": True},
                ),
            },
            {
                "label": "Battle Systems",
                "children": (
                    {"label": "Assault", "href": "/domains/assault"},
                    {"label": "Nyzul Isle", "href": "/nyzul"},
                ),
            },
            {
                "label": "Conflict / Battle",
                "planned": True,
                "children": (
                    {"label": "Ballista", "href": None, "planned": True},
                    {"label": "Besieged", "href": None, "planned": True},
                    {"label": "Brenner", "href": None, "planned": True},
                    {"label": "Campaign", "href": None, "planned": True},
                    {"label": "Colonization", "href": None, "planned": True},
                    {"label": "Expeditionary Force", "href": None, "planned": True},
                    {"label": "Garrison", "href": None, "planned": True},
                ),
            },
            {"label": "Combat", "href": None, "planned": True},
            {"label": "Dynamis", "href": None, "planned": True},
            {"label": "Escha", "href": None, "planned": True},
            {"label": "Hobbies", "href": None, "planned": True},
            {"label": "HELM", "href": None, "planned": True},
            {"label": "Events", "href": None, "planned": True},
            {"label": "Missions", "href": None, "planned": True},
            {"label": "Quests", "href": None, "planned": True},
            {
                "label": "Records of Eminence",
                "planned": True,
                "children": (
                    {"label": "General", "href": None, "planned": True},
                    {"label": "Unity", "href": None, "planned": True},
                    {"label": "Tutorial", "href": None, "planned": True},
                    {"label": "Quests", "href": None, "planned": True},
                    {"label": "Vanabout", "href": None, "planned": True},
                ),
            },
            {
                "label": "Trust",
                "planned": True,
                "children": (
                    {"label": "Misc", "href": None, "planned": True},
                    {"label": "Combat", "href": None, "planned": True},
                    {"label": "Quest", "href": None, "planned": True},
                ),
            },
            {"label": "Other", "href": None, "planned": True},
        ),
    },
    {
        "name": "Backport & Migration",
        "href": "/iddrift",
        "sections": (
            {"label": "ID Drift", "href": "/iddrift"},
            {"label": "Bindings", "href": "/backport/bindings"},
            {"label": "Lua Converter", "href": "/backport/lua-convert"},
            {"label": "SQL Converter", "href": "/backport/sql-convert"},
            {"label": "Backport Package (legacy)", "href": "/backport/package", "legacy": True},
        ),
    },
    {
        "name": "Captures",
        "href": "/captures",
        "sections": (
            {"label": "Library", "href": "/captures"},
            {"label": "Import", "href": "/captures/new"},
            {"label": "Search", "href": "/captures/search"},
            {"label": "Query", "href": "/captures/query"},
        ),
    },
    {
        "name": "Server",
        "href": "/zones",
        "sections": (
            {"label": "Zones", "href": "/zones"},
            {"label": "Entities", "href": "/entity"},
            {"label": "Items", "href": "/items"},
            {"label": "Key Items", "href": "/keyitems"},
            {"label": "SQL", "href": "/sql"},
            {"label": "Dialog", "href": "/dialog"},
            {"label": "Events / CSIDs", "href": "/events"},
            {"label": "Packets", "href": "/packets"},
            {"label": "Data Gaps", "href": "/gaps"},
            {
                "label": "3D Viewer",
                "href": "/zones/0/view3d",
                "active_patterns": (r"^/zones/[^/]+/view3d(?:_all)?$",),
            },
        ),
    },
    {
        "name": "Client",
        "href": "/modelviewer",
        "sections": (
            {"label": "Client Overview", "href": "/clientoverview"},
            {"label": "Model Viewer", "href": "/modelviewer"},
            {"label": "DAT Inspector", "href": "/datinspector"},
            {"label": "Binary Inspector", "href": "/binaryinspector"},
            {"label": "Dialog Drift", "href": "/dialogdrift"},
        ),
    },
    {
        "name": "Validation",
        "href": "/validation",
        "sections": (
            {"label": "Dashboard", "href": "/validation"},
            {"label": "Runs & Results", "href": "/validation/runs"},
            {"label": "Live Target", "href": "/validation/live-target"},
        ),
    },
    {
        "name": "Packages",
        "href": "/packages",
        "sections": (
            {"label": "Package Library", "href": "/packages"},
            {"label": "Scope Review", "href": "/packages/scope"},
            {"label": "Create Package", "href": "/packages/create", "mutation": True},
            {"label": "Review & Readiness", "href": "/packages/review"},
            {"label": "Backport Package (legacy)", "href": "/backport/package", "legacy": True},
        ),
    },
    {
        "name": "Tools",
        "href": "/llm",
        "sections": (
            {"label": "Research: LLM", "href": "/llm"},
            {"label": "Research: Wiki", "href": "/wiki"},
            {"label": "Editors: Zone Editor", "href": "/zoneplot", "mutation": True},
            {"label": "Editors: Item Editor", "href": "/itemedit", "mutation": True},
            {"label": "Lookup & Decode: Entity", "href": "/entity?shell=tools"},
            {"label": "Lookup & Decode: Packets", "href": "/packets?shell=tools"},
            {"label": "Diagnostics: Gaps", "href": "/gaps?shell=tools"},
            {"label": "Diagnostics: ID Drift", "href": "/iddrift?shell=tools"},
        ),
    },
    {
        "name": "Settings",
        "href": "/settings",
        "sections": (
            {"label": "General & Sources", "href": "/settings"},
            {"label": "Sources & Indexes", "href": "/"},
            {"label": "Backups & Recovery", "href": "/settings#backups"},
        ),
    },
)


def _route_pattern(path: str) -> re.Pattern[str]:
    escaped = re.escape(path)
    return re.compile("^" + re.sub(r"\\\{[^}]+\\\}", r"[^/]+", escaped) + "$")


@lru_cache(maxsize=1)
def route_owners() -> tuple[dict, ...]:
    payload = json.loads(ROUTE_MAP.read_text(encoding="utf-8"))
    rows = []
    for row in payload["routes"]:
        copy = dict(row)
        copy["pattern"] = _route_pattern(row["path"])
        copy["parameter_count"] = row["path"].count("{")
        rows.append(copy)
    rows.sort(key=lambda row: (row["parameter_count"], -len(row["path"])))
    return tuple(rows)


def route_owner(path: str, method: str = "GET") -> dict:
    method = method.upper()
    for row in route_owners():
        if row["method"] == method and row["pattern"].match(path):
            return {key: value for key, value in row.items() if key not in {"pattern", "parameter_count"}}
    return {"home": "Home / Project", "section": "Dashboard", "path": path, "method": method}


def _path_detail(path: str | Path | None) -> str | None:
    if not path:
        return None
    return str(Path(path))


def build_snapshot_context(
    settings: Mapping[str, str],
    *,
    default_topaz_root: str | Path,
    default_backport_root: str | Path,
    detected_client_path: str | None = None,
    path_exists: Callable[[Path], bool] = Path.exists,
) -> tuple[dict, ...]:
    """Describe only context supported by current settings/filesystem state.

    Existing settings contain roots, not selected canonical snapshot IDs or client build IDs.
    Those identities therefore remain UNKNOWN even when a real root is configured.
    """
    project_raw = settings.get("backport_root", "")
    project_path = Path(project_raw) if project_raw else Path(default_backport_root)
    project_value = project_path.name if path_exists(project_path) else "Not configured"
    project_detail = _path_detail(project_path) if path_exists(project_path) else None

    source_raw = settings.get("topaz_server_path", "")
    source_path = Path(source_raw) if source_raw else Path(default_topaz_root)
    source_configured = path_exists(source_path)

    target_raw = settings.get("dsp_server_path", "")
    target_path = Path(target_raw) if target_raw else None
    target_configured = bool(target_path and path_exists(target_path))

    client_raw = settings.get("ffxi_install_path", "")
    client_path = Path(client_raw or detected_client_path) if (client_raw or detected_client_path) else None
    client_configured = bool(client_path and path_exists(client_path))

    return (
        {
            "label": "Project",
            "value": project_value,
            "detail": project_detail or "No project workspace is available",
            "known": project_value != "Not configured",
        },
        {
            "label": "Source snapshot",
            "value": "UNKNOWN" if source_configured else "Not configured",
            "detail": f"Topaz root: {source_path}" if source_configured else "No active source snapshot or available Topaz root",
            "known": False,
        },
        {
            "label": "Target snapshot",
            "value": "UNKNOWN" if target_configured else "Not configured",
            "detail": f"DSP root: {target_path}" if target_configured else "No active target snapshot or configured DSP root",
            "known": False,
        },
        {
            "label": "Client build",
            "value": "UNKNOWN" if client_configured else "Not configured",
            "detail": f"FFXI install: {client_path}" if client_configured else "No detected or configured FFXI client install",
            "known": False,
        },
    )


def build_shell_context(
    *,
    path: str,
    method: str,
    settings: Mapping[str, str],
    default_topaz_root: str | Path,
    default_backport_root: str | Path,
    detected_client_path: str | None = None,
    path_exists: Callable[[Path], bool] = Path.exists,
    workspace_slug: str | None = None,
    shell_override: str | None = None,
) -> dict:
    owner = route_owner(path, method)
    planned_home = {"validation": "Validation", "packages": "Packages"}.get(workspace_slug or "")
    if planned_home:
        owner = {**owner, "home": planned_home, "section": "Dashboard"}
    # Contextual tools render their canonical route and keep its route-map ownership.
    # The optional shell marker only chooses the surrounding navigation workspace.
    tools_context_roots = ("/entity", "/packets", "/gaps", "/iddrift")
    if shell_override == "tools" and any(
        path == root or path.startswith(root + "/") for root in tools_context_roots
    ):
        owner = {**owner, "home": "Tools"}
    active = next((workspace for workspace in WORKSPACES if workspace["name"] == owner["home"]), WORKSPACES[0])
    section_rows = []
    linked = []
    for source_section in active["sections"]:
        section = dict(source_section)
        children = [dict(child) for child in source_section.get("children", ())]
        if children:
            section["children"] = children
        section_rows.append(section)
        candidates = children or [section]
        for candidate in candidates:
            href = candidate.get("href")
            if href and (
                path == href.split("?", 1)[0]
                or path.startswith(href.split("?", 1)[0].rstrip("/") + "/")
                or any(re.match(pattern, path) for pattern in candidate.get("active_patterns", ()))
            ):
                linked.append((section, candidate))
    selected = max(linked, key=lambda pair: len(pair[1]["href"]), default=None)
    for section in section_rows:
        section["active"] = False
        for child in section.get("children", ()):
            child["active"] = bool(selected and child.get("href") == selected[1].get("href"))
            if child["active"]:
                section["active"] = True
        if not section.get("children"):
            section["active"] = bool(selected and section.get("href") == selected[1].get("href"))
    return {
        "workspaces": WORKSPACES,
        "active_home": owner["home"],
        "active_section": owner["section"],
        "sections": tuple(section_rows),
        "snapshot_context": build_snapshot_context(
            settings,
            default_topaz_root=default_topaz_root,
            default_backport_root=default_backport_root,
            detected_client_path=detected_client_path,
            path_exists=path_exists,
        ),
    }
