"""Read-only Feature Trace state-surface API for Character Editor mission/quest drill-down."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .factory import open_character_editor
from .state_surface_bridge import build_character_state_surface

router = APIRouter(tags=["Character Editor State Surface"])


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz/LSB server root is configured")
    ctx = open_character_editor(root)
    try:
        yield ctx
    finally:
        ctx.close()


@router.get("/characters/{char_id}/state-surface.json")
def character_editor_state_surface(
    char_id: int,
    kind: str = Query(..., pattern="^(mission|quest)$"),
    area_id: int = Query(..., ge=0),
    entry_id: int = Query(..., ge=0),
):
    try:
        with _context() as ctx:
            payload = build_character_state_surface(
                ctx.service,
                int(char_id),
                kind=kind,
                area_id=int(area_id),
                entry_id=int(entry_id),
            )
            return JSONResponse(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# Attach below the Character Editor audit subrouter; gui.py already includes that router.
from .audit_gui import router as _character_subrouter

_character_subrouter.include_router(router)
