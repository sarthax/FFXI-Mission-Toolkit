"""Guarded DSP/Topaz TEST-only player-backed Auction House listing routes."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .player_listing import execute_legacy_test_player_listing, probe_player_listing_engines

router = APIRouter(prefix="/auction-house/test-write", tags=["Auction House Player Listing"])


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield root, ctx
    finally:
        ctx.close()


@router.get("/player-listing-readiness.json")
def player_listing_readiness():
    try:
        with _context() as (root, ctx):
            probe = probe_player_listing_engines(ctx.service.connection)
            return JSONResponse({
                "test_only": True,
                "ready_for_direct_transaction": probe.transactional,
                "engine_probe": probe.as_dict(),
                "server_root": str(root),
                "note": "Stock legacy MyISAM inventory is intentionally blocked from direct player-backed listing.",
            })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/player-listing.json")
def player_listing(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        with _context() as (root, ctx):
            result = execute_legacy_test_player_listing(
                service=ctx.service,
                server_root=root,
                environment=environment,
                seller_id=int(payload.get("seller_id") or 0),
                inventory_slot=int(payload.get("inventory_slot") or 0),
                item_id=int(payload.get("item_id") or 0),
                price=int(payload.get("price") or 0),
                stack=bool(payload.get("stack", False)),
                confirmation=str(payload.get("confirmation") or ""),
            )
            return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
