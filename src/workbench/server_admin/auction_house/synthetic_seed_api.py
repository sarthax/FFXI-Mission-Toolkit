"""DSP/Topaz TEST-only synthetic Auction House category seeding routes."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .activity import record_executor_result
from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .synthetic_seed import execute_synthetic_category_seed, preview_synthetic_category_seed

router = APIRouter(prefix="/auction-house/test-write", tags=["Auction House Synthetic Seeding"])


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


@router.post("/synthetic-category-preview.json")
def synthetic_category_preview(payload: dict = Body(...)):
    try:
        with _context() as ctx:
            return JSONResponse(preview_synthetic_category_seed(
                service=ctx.service,
                category_id=int(payload.get("category_id") or 0),
                price=int(payload.get("price") or 0),
                stack_mode=str(payload.get("stack_mode") or "single"),
                copies_per_item=int(payload.get("copies_per_item") or 1),
                limit_items=int(payload.get("limit_items") or 100),
            ))
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/synthetic-category-seed.json")
def synthetic_category_seed(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_synthetic_category_seed(
                service=ctx.service,
                environment=environment,
                seller_id=int(payload.get("seller_id") or 0),
                category_id=int(payload.get("category_id") or 0),
                price=int(payload.get("price") or 0),
                stack_mode=str(payload.get("stack_mode") or "single"),
                copies_per_item=int(payload.get("copies_per_item") or 1),
                limit_items=int(payload.get("limit_items") or 100),
                confirmation=str(payload.get("confirmation") or ""),
            )
        try:
            record_executor_result(environment=environment, result=result, request_payload=payload, operation="synthetic_category_seed")
        except Exception:
            pass
        return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
