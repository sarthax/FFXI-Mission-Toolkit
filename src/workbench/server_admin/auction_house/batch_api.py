"""Guarded DSP/Topaz Test-only Auction House batch action routes."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .activity import record_executor_result
from .batch_actions import execute_legacy_test_batch
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


@router.post("/batch-listings.json")
def batch_listing_action(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_batch(
                service=ctx.service,
                environment=environment,
                action=str(payload.get("action") or ""),
                targets=list(payload.get("targets") or []),
                confirmation=str(payload.get("confirmation") or ""),
            )
        try:
            record_executor_result(
                environment=environment,
                result=result,
                request_payload=payload,
                operation=f"batch_{str(payload.get('action') or 'unknown')}",
            )
        except Exception:
            pass
        return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
