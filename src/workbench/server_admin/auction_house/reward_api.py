"""Saved reward bundles and guarded DSP/Topaz Test Mog delivery API."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .reward_delivery import execute_reward_delivery, preview_reward_delivery
from .reward_templates import (
    RewardTemplateError,
    delete_reward_template,
    get_reward_template,
    list_reward_templates,
    save_reward_template,
)

router = APIRouter(prefix="/auction-house/rewards", tags=["Auction House Rewards"])


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


def _items(payload: dict) -> tuple[list[dict], dict | None]:
    template_id = str(payload.get("template_id") or "").strip()
    if template_id:
        template = get_reward_template(template_id)
        return list(template["items"]), template
    return list(payload.get("items") or []), None


@router.get("/templates.json")
def reward_templates_list():
    try:
        rows = list_reward_templates()
        return JSONResponse({"count": len(rows), "rows": rows})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/templates/save.json")
def reward_template_save(payload: dict = Body(...)):
    try:
        return JSONResponse(save_reward_template(
            template_id=(str(payload.get("template_id") or "").strip() or None),
            name=str(payload.get("name") or ""),
            items=list(payload.get("items") or []),
        ))
    except RewardTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/templates/delete.json")
def reward_template_delete(payload: dict = Body(...)):
    template_id = str(payload.get("template_id") or "").strip()
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")
    try:
        if not delete_reward_template(template_id):
            raise HTTPException(status_code=404, detail="Reward template was not found")
        return JSONResponse({"status": "deleted", "template_id": template_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/preview.json")
def reward_preview(payload: dict = Body(...)):
    try:
        items, template = _items(payload)
        with _context() as ctx:
            preview = preview_reward_delivery(
                service=ctx.service,
                mode=str(payload.get("recipient_mode") or "selected"),
                character_ids=[int(value) for value in (payload.get("character_ids") or [])],
                items=items,
            )
        return JSONResponse({"template": template, "preview": preview})
    except (RewardTemplateError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/execute.json")
def reward_execute(payload: dict = Body(...)):
    try:
        items, template = _items(payload)
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_reward_delivery(
                service=ctx.service,
                environment=environment,
                mode=str(payload.get("recipient_mode") or "selected"),
                character_ids=[int(value) for value in (payload.get("character_ids") or [])],
                items=items,
                preview_token=str(payload.get("preview_token") or ""),
                preview_id=str(payload.get("preview_id") or ""),
                replay_id=str(payload.get("replay_id") or ""),
                confirmation=str(payload.get("confirmation") or ""),
            )
        return JSONResponse({"template": template, "result": result})
    except (RewardTemplateError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
