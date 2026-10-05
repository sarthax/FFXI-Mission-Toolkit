"""Granular Auction House listing browser and guarded return-to-seller API."""
from __future__ import annotations

from contextlib import contextmanager
import sys

from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .listing_management import ListingFilter, browse_active_listings
from .safe_return import execute_legacy_test_safe_return

router = APIRouter(tags=["Auction House Listing Management"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))


def _sync_host_template_globals() -> None:
    for module_name in ("gui_server", "__main__"):
        host = sys.modules.get(module_name)
        host_templates = getattr(host, "templates", None) if host is not None else None
        host_env = getattr(host_templates, "env", None)
        host_globals = getattr(host_env, "globals", None)
        if host_globals:
            templates.env.globals.update(host_globals)
            return


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


@router.get("/auction-house/listing-manager", response_class=HTMLResponse)
def listing_manager_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_listing_manager.html",
        context={"title": "Auction House Listing Manager"},
    )


@router.get("/auction-house/listings.json")
def active_listing_browser(
    seller_id: int | None = Query(default=None, ge=1),
    seller_name: str | None = None,
    category_id: int | None = Query(default=None, ge=1),
    item_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Browse exact active AH rows by seller, category, item, or search text."""
    try:
        filters = ListingFilter(
            seller_id=seller_id,
            seller_name=seller_name,
            category_id=category_id,
            item_id=item_id,
            q=q,
            limit=limit,
        )
        with _context() as ctx:
            rows = browse_active_listings(ctx.service, filters)
            return JSONResponse({
                "filters": filters.as_dict(),
                "count": len(rows),
                "rows": rows,
                "actions": {
                    "preview_buy": "/auction-house/admin/purchase/preview.json",
                    "return_to_seller": "/auction-house/test-write/return-to-seller.json",
                },
            })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/auction-house/test-write/return-to-seller.json")
def return_listing_to_seller(payload: dict = Body(...)):
    """Cancel one DSP/Topaz Test listing using the safest verified return strategy."""
    try:
        auction_id = int(payload.get("auction_id") or 0)
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_safe_return(
                service=ctx.service,
                environment=environment,
                auction_id=auction_id,
                confirmation=confirmation,
            )
            return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
