"""Saved reward bundles and guarded DSP/Topaz Test Mog delivery API."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked, evaluate_legacy_test_write_gate
from .reward_campaigns import record_campaign
from .reward_schedules import create_schedule, list_schedules, cancel_schedule
from .reward_attempt_journal import get_attempt, list_attempts
from .recovery_journal import list_cases
from .augmented_rewards import inspect_augmented_reward
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
        # items sent with the request win (the operator may have edited a loaded template); the template is kept for history
        return list(payload.get("items") or template["items"]), template
    return list(payload.get("items") or []), None


@router.get("/schedules.json")
def schedules_list():
    return JSONResponse({"rows": list_schedules()})


@router.post("/schedules/create.json")
def schedule_reward(payload: dict = Body(...)):
    """One-time Test-only schedule; recipients are frozen at approval time."""
    try:
        environment = get_active_server_identity()
        items, _template = _items(payload)
        mode = str(payload.get("recipient_mode") or "selected")
        with _context() as ctx:
            gate = evaluate_legacy_test_write_gate(
                environment=environment,
                schema_family_hint=ctx.service.schema.family_hint,
                confirmation=str(payload.get("confirmation") or ""),
            )
            if not gate.ready:
                raise LegacyTestExecutionBlocked("Test-write requirements or exact profile confirmation failed")
            preview = preview_reward_delivery(
                service=ctx.service, mode=mode,
                character_ids=[int(i) for i in (payload.get("character_ids") or [])],
                items=items,
            )
        frozen_ids = [r["char_id"] for r in preview["recipients"]]
        return JSONResponse(create_schedule(
            due_utc=str(payload.get("due_utc") or ""),
            environment=environment,
            # Freeze all/account membership rather than re-evaluating recipients later.
            recipient_mode="selected", character_ids=frozen_ids, items=items,
            confirmation=str(payload.get("confirmation") or ""),
        ))
    except (RewardTemplateError, LegacyTestExecutionBlocked, ValueError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/schedules/cancel.json")
def schedule_cancel(payload: dict = Body(...)):
    try:
        return JSONResponse(cancel_schedule(str(payload.get("schedule_id") or "")))
    except (RewardTemplateError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/attempts.json")
def reward_attempts_list():
    return JSONResponse({"rows": list_attempts()})


@router.get("/attempts/{replay_id}.json")
def reward_attempt_detail(replay_id: str):
    try:
        return JSONResponse(get_attempt(replay_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/myisam-recovery.json")
def myisam_recovery_cases():
    return JSONResponse({"rows": list_cases()})


@router.get("/augments/catalog.json")
def augmented_reward_catalog():
    """Read verified augment IDs/effects from the active server's source files."""
    from workbench.editors.character.equipment_augments import augment_catalog
    root = get_active_server_root()
    if root is None:
        raise HTTPException(status_code=409, detail="Select an active server with an augment catalog")
    catalog = augment_catalog(root)
    return JSONResponse(catalog)


@router.post("/augments/inspect.json")
def augmented_reward_inspection(payload: dict = Body(...)):
    try:
        environment = get_active_server_identity()
        item_id = int(payload.get("item_id") or 0)
        with _context() as ctx:
            if not ctx.service.item_snapshot(item_id):
                raise LegacyTestExecutionBlocked("Item does not exist in active server data")
            preview = inspect_augmented_reward(
                family=str(environment.get("family") or ""),
                item_id=item_id,
                augments=list(payload.get("augments") or []),
                server_root=get_active_server_root(),
            )
        return JSONResponse(preview)
    except (LegacyTestExecutionBlocked, ValueError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


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
        recipient_mode = str(payload.get("recipient_mode") or "selected")
        character_ids = [int(value) for value in (payload.get("character_ids") or [])]
        preview_id = str(payload.get("preview_id") or "")
        replay_id = str(payload.get("replay_id") or "")
        with _context() as ctx:
            result = execute_reward_delivery(
                service=ctx.service,
                environment=environment,
                mode=recipient_mode,
                character_ids=character_ids,
                items=items,
                preview_token=str(payload.get("preview_token") or ""),
                preview_id=preview_id,
                replay_id=replay_id,
                confirmation=str(payload.get("confirmation") or ""),
            )
        campaign = record_campaign(
            environment=environment,
            template=template,
            items=items,
            recipient_mode=recipient_mode,
            recipient_count=int(result.get("recipient_count") or 0),
            preview_id=preview_id,
            replay_id=replay_id,
            result=result,
        )
        return JSONResponse({"template": template, "result": result, "campaign": campaign})
    except (RewardTemplateError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
