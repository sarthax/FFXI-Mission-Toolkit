"""Copy-only Server GM command browser; no execution or chat transport."""
from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from workbench.runtime.legacy_settings import get_active_server_root
from .catalog import CATEGORIES, catalog_commands
from .lookup import KINDS, lookup
from ._page import PAGE

router = APIRouter(prefix="/server/gm", tags=["Server GM Command Catalog"])


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
def id_lookup(kind: str, q: str = "", limit: int = 30):
    """Search the active server's own tables for IDs (items, key items, zones, ...)."""
    root = get_active_server_root()
    if kind not in KINDS:
        raise HTTPException(400, "Unknown lookup kind")
    if not root or not Path(root).is_dir():
        raise HTTPException(409, "Configure an active local DSP server checkout first")
    try:
        return {"kind": kind, "results": lookup(root, kind, q[:64], limit)}
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Lookup source missing in the active server checkout") from exc


@router.get("", response_class=HTMLResponse)
def gm_command_page():
    return HTMLResponse(PAGE)
