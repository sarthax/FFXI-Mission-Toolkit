"""Audit history and guarded undo routes for the Character Editor."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .audit import read_audit_events
from .audit_undo import apply_undo, build_undo_plan
from .factory import open_character_editor

router = APIRouter()


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz/LSB server root is configured")
    ctx = open_character_editor(root)
    try:
        yield ctx
    finally:
        ctx.close()


def _safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"bytes": len(raw), "sha_preview": raw[:8].hex()}
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def _summary(event: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(event.get("metadata") or {})
    # Never send raw before/after state through the history list. Exact restore data remains on disk.
    if "changes" in metadata and isinstance(metadata["changes"], dict):
        metadata = {"changes": metadata["changes"]}
    elif "original_event_id" in metadata:
        metadata = {"original_event_id": metadata["original_event_id"]}
    else:
        metadata = {}
    return {
        "event_id": event.get("event_id"),
        "timestamp_utc": event.get("timestamp_utc"),
        "operation": event.get("operation"),
        "char_id": event.get("char_id"),
        "adapter_family": event.get("adapter_family"),
        "status": event.get("status"),
        "target": _safe(event.get("target") or {}),
        "metadata": _safe(metadata),
        "backup_path": event.get("backup_path"),
        "undo_supported": bool(event.get("undo_supported")),
    }


@router.get("/characters/{char_id}/audit.json")
def character_editor_audit_history(char_id: int, limit: int = Query(100, ge=1, le=500)):
    try:
        with _context() as ctx:
            if not ctx.service.character_exists(char_id):
                raise HTTPException(status_code=404, detail="Character not found")
            events = [_summary(event) for event in read_audit_events(char_id=char_id, limit=limit)]
            return JSONResponse({"events": events})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/characters/{char_id}/audit/{event_id}/undo/preview")
def character_editor_audit_undo_preview(char_id: int, event_id: str):
    try:
        with _context() as ctx:
            plan = build_undo_plan(ctx.service.connection, event_id=event_id, adapter_family=ctx.service.adapter_family)
            if plan.char_id not in (0, int(char_id)):
                raise HTTPException(status_code=404, detail="Audit event does not belong to this character")
            payload = plan.as_dict()
            payload["before"] = _safe(payload.get("before"))
            payload["after"] = _safe(payload.get("after"))
            return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/characters/{char_id}/audit/{event_id}/undo/apply")
async def character_editor_audit_undo_apply(char_id: int, event_id: str, request: Request):
    try:
        body = await request.json()
        if body.get("approved") is not True:
            raise HTTPException(status_code=400, detail="Explicit approved=true confirmation is required")
        with _context() as ctx:
            preview = build_undo_plan(ctx.service.connection, event_id=event_id, adapter_family=ctx.service.adapter_family)
            if preview.char_id != int(char_id):
                raise HTTPException(status_code=404, detail="Audit event does not belong to this character")
            result = apply_undo(ctx.service.connection, event_id=event_id, adapter_family=ctx.service.adapter_family, approved=True)
            return JSONResponse(_safe(result))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
