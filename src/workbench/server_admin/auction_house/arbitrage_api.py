"""Read-only AH vs vendor arbitrage endpoint for the console."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .arbitrage import compute
from .factory import open_auction_house

router = APIRouter(tags=["Auction House Console"])


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield ctx, root
    finally:
        ctx.close()


@router.get("/auction-house/console/arbitrage.json")
def console_arbitrage(min_profit: int = Query(default=1, ge=0, le=100_000_000)):
    try:
        with _context() as (ctx, root):
            return JSONResponse(compute(ctx.service, root, min_profit=min_profit))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
