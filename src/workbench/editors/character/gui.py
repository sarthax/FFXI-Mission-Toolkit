"""FastAPI router for the Character Editor workspace.

The heavy database/schema/item logic stays in the Character Editor services.  This module is a
thin HTTP/presentation adapter so gui_server.py only needs to register one packaged router.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .factory import open_character_editor

router = APIRouter(prefix="/character-editor", tags=["Character Editor"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))


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


def _safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"hex": raw.hex(), "bytes": len(raw)}
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def _error(exc: Exception, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@router.get("", response_class=HTMLResponse)
def character_editor_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="character_editor.html",
        context={"title": "Character Editor"},
    )


@router.get("/status.json")
def character_editor_status():
    try:
        with _context() as ctx:
            return JSONResponse(_safe(ctx.public_status()))
    except Exception as exc:
        raise _error(exc, 503)


@router.get("/characters.json")
def character_editor_characters(q: str = "", limit: int = Query(50, ge=1, le=200)):
    try:
        with _context() as ctx:
            return JSONResponse({"rows": _safe(ctx.service.search_characters(q, limit))})
    except Exception as exc:
        raise _error(exc, 503)


@router.get("/items.json")
def character_editor_items(q: str = "", limit: int = Query(100, ge=1, le=500)):
    try:
        with _context() as ctx:
            rows = ctx.service.search_items(q, limit=limit)
            return JSONResponse({"rows": _safe(rows)})
    except Exception as exc:
        raise _error(exc, 503)


@router.get("/items/{item_id}.json")
def character_editor_item(item_id: int):
    try:
        with _context() as ctx:
            row = ctx.service.get_item(item_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Item not found")
            return JSONResponse(_safe(row))
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(exc, 503)


@router.get("/characters/{char_id}.json")
def character_editor_character(char_id: int):
    try:
        with _context() as ctx:
            return JSONResponse(_safe(ctx.service.load_character(char_id, include_rows=False)))
    except KeyError as exc:
        raise _error(exc, 404)
    except Exception as exc:
        raise _error(exc, 503)


@router.get("/characters/{char_id}/inventory.json")
def character_editor_inventory(char_id: int):
    try:
        with _context() as ctx:
            rows = ctx.service.load_table(char_id, "char_inventory")
            item_cache: dict[int, dict[str, Any] | None] = {}
            enriched = []
            for row in rows:
                item_id = int(row.get("itemId") or row.get("item_id") or 0)
                if item_id not in item_cache:
                    item_cache[item_id] = ctx.service.get_item(item_id) if item_id else None
                item = item_cache[item_id]
                out = dict(row)
                out["item"] = item
                enriched.append(out)
            return JSONResponse({"rows": _safe(enriched)})
    except KeyError as exc:
        raise _error(exc, 404)
    except Exception as exc:
        raise _error(exc, 503)


@router.post("/characters/{char_id}/items/preview")
async def character_editor_preview_item(char_id: int, request: Request):
    try:
        body = await request.json()
        with _context() as ctx:
            plan = ctx.service.preview_add_item(
                char_id,
                int(body.get("item_id")),
                quantity=int(body.get("quantity", 1)),
                location=int(body.get("location", 0)),
            )
            return JSONResponse(_safe(plan))
    except Exception as exc:
        raise _error(exc)


@router.post("/characters/{char_id}/items/add")
async def character_editor_add_item(char_id: int, request: Request):
    try:
        body = await request.json()
        if body.get("approved") is not True:
            raise HTTPException(status_code=400, detail="Explicit approved=true confirmation is required")
        with _context() as ctx:
            plan = ctx.service.preview_add_item(
                char_id,
                int(body.get("item_id")),
                quantity=int(body.get("quantity", 1)),
                location=int(body.get("location", 0)),
            )
            result = ctx.service.add_item(plan, approved=True)
            return JSONResponse(_safe(result))
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(exc)
