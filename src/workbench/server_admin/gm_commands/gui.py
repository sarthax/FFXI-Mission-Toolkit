"""Copy-only Server GM command browser; no execution or chat transport."""
from __future__ import annotations

from html import escape
from pathlib import Path

import sys

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_root
from .catalog import CATEGORIES, catalog_commands
from .lookup import KINDS, lookup

router = APIRouter(prefix="/server/gm", tags=["Server GM Command Catalog"])
from workbench.runtime.paths import GUI_ROOT

_TEMPLATES = GUI_ROOT / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES))


def _sync_host_template_globals() -> None:
    """Reuse the main GUI's shared base.html globals (top navigation) when hosted."""
    for module_name in ("workbench.app.host", "__main__"):
        host_env = getattr(getattr(sys.modules.get(module_name), "templates", None), "env", None)
        host_globals = getattr(host_env, "globals", None)
        if host_globals:
            templates.env.globals.update(host_globals)
            return


def _catalog():
    root = get_active_server_root()
    if not root or not Path(root).is_dir():
        raise HTTPException(409, "Configure an active local DSP server checkout first")
    try:
        return catalog_commands(root)
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Active server checkout has no readable GM command catalog") from exc


@router.get("/commands")
def commands():
    """Read-only metadata; raw Lua and arbitrary host paths are not served."""
    return {"commands": _catalog(), "categories": CATEGORIES, "execution_enabled": False}


@router.get("/lookup")
def id_lookup(kind: str, q: str = "", limit: int = 30, log: int | None = None):
    """Search the active server's own tables for IDs (items, key items, zones, ...)."""
    root = get_active_server_root()
    if kind not in KINDS:
        raise HTTPException(400, "Unknown lookup kind")
    if not root or not Path(root).is_dir():
        raise HTTPException(409, "Configure an active local DSP server checkout first")
    try:
        return {"kind": kind, "results": lookup(root, kind, q[:64], limit, log)}
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Lookup source missing in the active server checkout") from exc


@router.get("", response_class=HTMLResponse)
def gm_command_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(request=request, name="server_gm_commands.html",
                                      context={"title": "GM Command Center"})
