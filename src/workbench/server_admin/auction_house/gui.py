"""FastAPI presentation adapter for read-only Auction House administration."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import GUI_ROOT
from workbench.editors.items import client_asset_cache

from .analytics import economy_summary, price_trends, search_items
from .factory import open_auction_house

router = APIRouter(prefix="/auction-house", tags=["Auction House Administration"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz/LSB server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield ctx
    finally:
        ctx.close()


def _error(exc: Exception, status: int = 503) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@router.get("", response_class=HTMLResponse)
def auction_house_page(request: Request):
    return templates.TemplateResponse(request=request, name="auction_house.html", context={"title": "Auction House Admin"})


@router.get("/status.json")
def status():
    try:
        with _context() as ctx:
            return JSONResponse(ctx.public_status())
    except Exception as exc:
        raise _error(exc)


@router.get("/overview.json")
def overview(days: int = Query(30, ge=1, le=3650)):
    try:
        with _context() as ctx:
            return JSONResponse(economy_summary(ctx.service, days=days))
    except Exception as exc:
        raise _error(exc)


@router.get("/categories.json")
def categories():
    try:
        with _context() as ctx:
            return JSONResponse({"rows": ctx.service.categories()})
    except Exception as exc:
        raise _error(exc)


@router.get("/items.json")
def items(q: str = "", category_id: int | None = None, limit: int = Query(100, ge=1, le=500)):
    try:
        with _context() as ctx:
            return JSONResponse({"rows": search_items(ctx.service, q, category_id=category_id, limit=limit)})
    except Exception as exc:
        raise _error(exc)


@router.get("/items/{item_id}.json")
def item_detail(item_id: int, history_limit: int = Query(100, ge=1, le=1000)):
    try:
        with _context() as ctx:
            matches = search_items(ctx.service, str(item_id), limit=2)
            item = next((row for row in matches if row["item_id"] == item_id), None)
            if item is None:
                raise HTTPException(status_code=404, detail="Auction House item not found")
            return JSONResponse({
                "item": item,
                "active_listings": ctx.service.active_listings(item_id),
                "history": ctx.service.sale_history(item_id, limit=history_limit),
                "trends": {
                    "7": price_trends(ctx.service, item_id, days=7),
                    "30": price_trends(ctx.service, item_id, days=30),
                    "90": price_trends(ctx.service, item_id, days=90),
                },
            })
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(exc)


@router.get("/items/{item_id}/history.json")
def item_history(item_id: int, limit: int = Query(100, ge=1, le=1000)):
    try:
        with _context() as ctx:
            return JSONResponse({"rows": ctx.service.sale_history(item_id, limit=limit)})
    except Exception as exc:
        raise _error(exc)


@router.get("/items/{item_id}/trends.json")
def item_trends(item_id: int, days: int = Query(30, ge=1, le=3650)):
    try:
        with _context() as ctx:
            return JSONResponse({"rows": price_trends(ctx.service, item_id, days=days), "days": days})
    except Exception as exc:
        raise _error(exc)


@router.get("/items/{item_id}/icon.png")
def item_icon(item_id: int):
    try:
        entry = client_asset_cache.ensure_item(item_id)
    except Exception as exc:
        raise _error(exc)
    if entry is None or entry.icon_path is None:
        raise HTTPException(status_code=404, detail="Client icon is unavailable")
    return FileResponse(entry.icon_path, media_type="image/png")
