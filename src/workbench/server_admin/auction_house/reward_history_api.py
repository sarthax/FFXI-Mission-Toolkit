"""Read-only reward campaign history and guarded retry preview API."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .reward_campaigns import failed_recipient_ids, get_campaign, list_campaigns
from .reward_delivery import preview_reward_delivery

router = APIRouter(prefix="/auction-house/reward-history", tags=["Auction House Reward History"])


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


@router.get(".json")
def campaigns_list(status: str | None = Query(default=None), template_id: str | None = Query(default=None),
                   limit: int = Query(default=100, ge=1, le=500)):
    try:
        rows = list_campaigns(status=status, template_id=template_id, limit=limit)
        return JSONResponse({"count": len(rows), "rows": rows})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{campaign_id}.json")
def campaign_detail(campaign_id: str):
    try:
        return JSONResponse(get_campaign(campaign_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def validate_retry_environment(source: dict, active: dict) -> None:
    """Never carry a campaign retry into another named server environment.

    Stable profile identity is required; missing or mismatched evidence fails closed.
    This is a comparison guard, not a substitute for execution-time Test gates.
    """
    keys = ("name", "family", "environment")
    for key in keys:
        original = str(source.get(key) or "").strip().lower()
        selected = str(active.get(key) or "").strip().lower()
        if not original or not selected or original != selected:
            raise LegacyTestExecutionBlocked(
                "Reward retry requires the original named server environment; "
                f"{key} is missing or changed"
            )


@router.post("/{campaign_id}/retry-preview.json")
def campaign_retry_preview(campaign_id: str, payload: dict = Body(default={})):
    """Preview a retry for failed recipients only; never include prior successful recipients."""
    try:
        campaign = get_campaign(campaign_id)
        validate_retry_environment(campaign.get("environment") or {}, get_active_server_identity())
        failed_ids = failed_recipient_ids(campaign_id)
        if not failed_ids:
            raise LegacyTestExecutionBlocked("This campaign has no failed recipients to retry")
        with _context() as ctx:
            preview = preview_reward_delivery(
                service=ctx.service,
                mode="selected",
                character_ids=failed_ids,
                items=list(campaign.get("items") or []),
            )
        return JSONResponse({
            "source_campaign_id": campaign_id,
            "source_status": campaign.get("overall_status"),
            "failed_recipient_count": len(failed_ids),
            "character_ids": failed_ids,
            "items": campaign.get("items") or [],
            "preview": preview,
            "note": "Retry preview includes failed recipients only. Execute through the normal reward endpoint with a fresh Test confirmation.",
        })
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
