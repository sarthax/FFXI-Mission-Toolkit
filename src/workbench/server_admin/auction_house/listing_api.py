"""Granular Auction House listing browser and guarded return-to-seller API."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .listing_management import ListingFilter, browse_active_listings, execute_legacy_test_return_to_seller

router = APIRouter(tags=["Auction House Listing Management"])


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
    """Cancel one DSP/Topaz Test listing and atomically return its item to seller Inventory."""
    try:
        auction_id = int(payload.get("auction_id") or 0)
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_return_to_seller(
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
