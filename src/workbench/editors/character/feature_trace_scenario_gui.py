"""Scenario-driven Feature Trace page mounted through the packaged GUI router.

This is intentionally read-only. It exposes the new resolver/mode contracts without replacing
the existing technical /features/trace page, which remains available for deep diagnostics.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_modes import mode_options, normalize_mode
from workbench.runtime.paths import DATABASE_PATH, GUI_ROOT, repo_path

router = APIRouter(tags=["Scenario Feature Trace"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))
WORKBENCH_DB = repo_path("workbench.db")


def _open(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


@router.get("/scenario-trace", response_class=HTMLResponse)
def scenario_feature_trace(
    request: Request,
    q: str = "",
    mode: str = "implementation",
    depth: int = Query(3, ge=0, le=8),
    direction: str = "both",
):
    selected = normalize_mode(mode)
    if direction not in {"out", "in", "both"}:
        direction = "both"
    resolution = None
    result = None
    error = None
    graph_con = None
    catalog_con = None
    try:
        if not WORKBENCH_DB.is_file():
            raise RuntimeError("Canonical Workbench graph is not available. Build/import workbench.db first.")
        graph_con = _open(WORKBENCH_DB)
        catalog_con = _open(DATABASE_PATH)
        if q.strip():
            resolution = feature_trace.resolve_query(graph_con, q.strip(), catalog_con)
            if resolution.get("status") == "RESOLVED" and resolution.get("root"):
                result = feature_trace.trace(
                    graph_con,
                    resolution["root"],
                    depth,
                    direction,
                    catalog_con,
                    mode=selected.mode_id,
                )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if graph_con is not None:
            graph_con.close()
        if catalog_con is not None:
            catalog_con.close()

    return templates.TemplateResponse(request, "feature_trace_scenario.html", {
        "request": request,
        "q": q,
        "mode": selected.mode_id,
        "mode_info": selected,
        "mode_options": mode_options(),
        "depth": depth,
        "direction": direction,
        "resolution": resolution,
        "result": result,
        "error": error,
    })


# Attach to the Character Editor audit subrouter, which is already mounted by gui.py.
# The URL is therefore /character-editor/scenario-trace during the migration period.
from .audit_gui import router as _character_subrouter

_character_subrouter.include_router(router)
