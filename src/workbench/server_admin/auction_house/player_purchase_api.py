"""Guarded DSP/Topaz TEST-only exact-row player purchase route."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .activity import record_executor_result
from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .player_purchase import execute_legacy_test_player_purchase, probe_player_purchase_engines

router = APIRouter(prefix="/auction-house/test-write", tags=["Auction House Listing Management"])


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield ctx
    finally:
        ctx.close()


@router.get("/player-purchase-readiness.json")
def player_purchase_readiness():
    try:
        with _context() as ctx:
            return JSONResponse(probe_player_purchase_engines(ctx.service.connection).as_dict())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/player-purchase.json")
def player_purchase(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_player_purchase(
                service=ctx.service,
                environment=environment,
                auction_id=int(payload.get("auction_id") or 0),
                expected_price=int(payload.get("expected_price") or 0),
                buyer_id=int(payload.get("buyer_id") or 0),
                confirmation=str(payload.get("confirmation") or ""),
            )
        try:
            record_executor_result(environment=environment, result=result, request_payload=payload, operation="player_purchase")
        except Exception:
            pass
        return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
