"""Client DAT cache routes shared by Settings and Character Editor inventory."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from workbench.editors.items.client_asset_cache import (
    build_source,
    cache_status,
    clear_cache,
    ensure_item,
)

router = APIRouter(prefix="/client-cache", tags=["Client DAT Cache"])


@router.get("/status.json")
def client_cache_status():
    try:
        return JSONResponse(cache_status())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/build-source")
async def client_cache_build_source(request: Request):
    try:
        body = await request.json()
        category = str(body.get("category") or "").strip()
        if not category:
            raise ValueError("category is required")
        return JSONResponse(build_source(category))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/clear")
def client_cache_clear():
    try:
        return JSONResponse(clear_cache())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/items/{item_id}.json")
def client_cache_item(item_id: int):
    try:
        entry = ensure_item(item_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if entry is None or not entry.available:
        raise HTTPException(status_code=404, detail="Client item record not found")
    return JSONResponse(
        {
            "item_id": entry.item_id,
            "cache_hit": entry.cache_hit,
            "metadata": entry.metadata,
            "icon_available": bool(entry.icon_path),
            "icon_sha256": entry.icon_sha256,
            "source": {
                "category": entry.source.category,
                "rom_path": entry.source.rom_path,
                "record_index": entry.source.record_index,
            },
        }
    )


@router.get("/icons/{item_id}.png")
def client_cache_icon(item_id: int):
    try:
        entry = ensure_item(item_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if entry is None or not entry.available or entry.icon_path is None:
        raise HTTPException(status_code=404, detail="Client item icon not found")
    headers = {"Cache-Control": "public, max-age=3600"}
    if entry.icon_sha256:
        headers["ETag"] = f'"{entry.icon_sha256}"'
    return FileResponse(entry.icon_path, media_type="image/png", headers=headers)


# Character Editor is already registered on the live app. Attach this subrouter without adding
# another gui_server.py registration point.
from .audit_gui import router as _character_subrouter

_character_subrouter.include_router(router)
