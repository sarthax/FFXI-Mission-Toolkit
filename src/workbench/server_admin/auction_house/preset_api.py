"""Saved Auction House administration preset API."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .presets import PresetError, delete_preset, get_preset, list_presets, save_preset, seed_builtin_presets
from .rule_cleanup import criteria_from_payload, execute_cleanup, preview_cleanup
from .synthetic_seed import execute_synthetic_category_seed, preview_synthetic_category_seed

router = APIRouter(prefix="/auction-house/presets", tags=["Auction House Presets"])


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


def _live_preview(service, preset: dict) -> dict:
    config = dict(preset.get("config") or {})
    if preset["kind"] == "cleanup":
        return preview_cleanup(service, criteria_from_payload(config))
    if preset["kind"] == "synthetic_seed":
        return preview_synthetic_category_seed(
            service=service,
            category_id=int(config.get("category_id") or 0),
            price=int(config.get("price") or 0),
            stack_mode=str(config.get("stack_mode") or "single"),
            copies_per_item=int(config.get("copies_per_item") or 1),
            limit_items=int(config.get("limit_items") or 100),
        )
    raise PresetError("Unsupported Auction House preset kind")


def _preset_preview_token(preset: dict, preview: dict) -> str:
    if preset["kind"] == "cleanup":
        binding = {
            "criteria": preview.get("criteria"),
            "cleanup_preview_token": preview.get("preview_token"),
        }
    elif preset["kind"] == "synthetic_seed":
        binding = {
            "category_id": preview.get("category_id"),
            "price": preview.get("price"),
            "stack_mode": preview.get("stack_mode"),
            "copies_per_item": preview.get("copies_per_item"),
            "limit_items": preview.get("limit_items"),
            "items": preview.get("items"),
        }
    else:
        raise PresetError("Unsupported Auction House preset kind")
    material = {
        "preset_id": preset["preset_id"],
        "updated_at_utc": preset["updated_at_utc"],
        "kind": preset["kind"],
        "config": preset["config"],
        "binding": binding,
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


@router.get(".json")
def presets_list(kind: str | None = Query(default=None)):
    try:
        seed_builtin_presets()
        rows = list_presets(kind=kind)
        return JSONResponse({"count": len(rows), "rows": rows})
    except PresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/save.json")
def presets_save(payload: dict = Body(...)):
    try:
        row = save_preset(
            preset_id=(str(payload.get("preset_id") or "").strip() or None),
            name=str(payload.get("name") or ""),
            kind=str(payload.get("kind") or ""),
            config=dict(payload.get("config") or {}),
        )
        return JSONResponse(row)
    except PresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/delete.json")
def presets_delete(payload: dict = Body(...)):
    preset_id = str(payload.get("preset_id") or "").strip()
    if not preset_id:
        raise HTTPException(status_code=400, detail="preset_id is required")
    try:
        deleted = delete_preset(preset_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Auction House preset was not found")
        return JSONResponse({"status": "deleted", "preset_id": preset_id})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/preview.json")
def presets_preview(payload: dict = Body(...)):
    """Resolve a saved preset against current live data without mutating the server."""
    try:
        preset = get_preset(str(payload.get("preset_id") or ""))
        with _context() as ctx:
            preview = _live_preview(ctx.service, preset)
        return JSONResponse({
            "preset": preset,
            "preview": preview,
            "preset_preview_token": _preset_preview_token(preset, preview),
        })
    except (PresetError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/execute.json")
def presets_execute(payload: dict = Body(...)):
    """Re-preview a preset and delegate to its existing guarded executor only if unchanged."""
    try:
        preset = get_preset(str(payload.get("preset_id") or ""))
        expected_token = str(payload.get("preset_preview_token") or "")
        confirmation = str(payload.get("confirmation") or "")
        if not expected_token:
            raise LegacyTestExecutionBlocked("A fresh preset preview is required before execution")
        environment = get_active_server_identity()
        config = dict(preset.get("config") or {})
        with _context() as ctx:
            preview = _live_preview(ctx.service, preset)
            live_token = _preset_preview_token(preset, preview)
            if live_token != expected_token:
                raise LegacyTestExecutionBlocked("Saved preset preview is stale; preview the live target set again")
            if preset["kind"] == "cleanup":
                result = execute_cleanup(
                    service=ctx.service,
                    environment=environment,
                    criteria=criteria_from_payload(preview["criteria"]),
                    preview_token=str(preview.get("preview_token") or ""),
                    action=str(config.get("default_action") or "return_to_seller"),
                    confirmation=confirmation,
                )
            elif preset["kind"] == "synthetic_seed":
                result = execute_synthetic_category_seed(
                    service=ctx.service,
                    environment=environment,
                    seller_id=int(config.get("seller_id") or 0),
                    category_id=int(config.get("category_id") or 0),
                    price=int(config.get("price") or 0),
                    stack_mode=str(config.get("stack_mode") or "single"),
                    copies_per_item=int(config.get("copies_per_item") or 1),
                    limit_items=int(config.get("limit_items") or 100),
                    confirmation=confirmation,
                )
            else:
                raise PresetError("Unsupported Auction House preset kind")
        return JSONResponse({"preset": preset, "preset_preview_token": live_token, "result": result})
    except (PresetError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
