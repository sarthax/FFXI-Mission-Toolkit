"""Guarded DSP/Topaz TEST-only administrative Auction House cleanup route."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .activity import record_executor_result
from .admin_buy import execute_legacy_test_admin_buy
from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked

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


@router.post("/admin-buy.json")
def admin_buy_listing(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_admin_buy(
                service=ctx.service,
                environment=environment,
                auction_id=int(payload.get("auction_id") or 0),
                expected_price=int(payload.get("expected_price") or 0),
                confirmation=str(payload.get("confirmation") or ""),
            )
        try:
            record_executor_result(environment=environment, result=result, request_payload=payload, operation="admin_buy")
        except Exception:
            pass
        return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
