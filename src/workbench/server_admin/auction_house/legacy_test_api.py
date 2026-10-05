"""DSP/Topaz TEST-only Auction House write API.

Kept separate from the read/preview router so write-capable endpoints have an explicit, narrow
surface and can remain hard-blocked outside named Test environments.
"""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import (
    LegacyTestExecutionBlocked,
    evaluate_legacy_test_write_gate,
    execute_legacy_test_price_change,
    execute_legacy_test_synthetic_listing,
)

router = APIRouter(prefix="/auction-house/test-write", tags=["Auction House Test Writes"])


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


@router.post("/readiness.json")
def legacy_test_write_readiness(payload: dict = Body(default={})):
    """Evaluate write gates without mutating the server database."""
    try:
        environment = get_active_server_identity()
        confirmation = str(payload.get("confirmation") or "")
        with _context() as ctx:
            gate = evaluate_legacy_test_write_gate(
                environment=environment,
                schema_family_hint=ctx.service.schema.family_hint,
                confirmation=confirmation,
            )
            return JSONResponse(gate.as_dict())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/price-change.json")
def legacy_test_price_change(payload: dict = Body(...)):
    """Change one active DSP/Topaz Test listing price through the guarded executor."""
    try:
        auction_id = int(payload.get("auction_id") or 0)
        expected_price = int(payload.get("expected_price") or 0)
        new_price = int(payload.get("new_price") or 0)
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_price_change(
                service=ctx.service,
                environment=environment,
                auction_id=auction_id,
                expected_price=expected_price,
                new_price=new_price,
                confirmation=confirmation,
            )
            return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/synthetic-listing.json")
def legacy_test_synthetic_listing(payload: dict = Body(...)):
    """Insert one explicit admin-created DSP/Topaz Test listing.

    This is deliberately not a player listing: it does not remove seller inventory or charge the
    normal listing fee. The response reports the synthetic supply injection explicitly.
    """
    try:
        item_id = int(payload.get("item_id") or 0)
        seller_id = int(payload.get("seller_id") or 0)
        price = int(payload.get("price") or 0)
        stack = bool(payload.get("stack", False))
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_legacy_test_synthetic_listing(
                service=ctx.service,
                environment=environment,
                item_id=item_id,
                seller_id=seller_id,
                price=price,
                stack=stack,
                confirmation=confirmation,
            )
            return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
