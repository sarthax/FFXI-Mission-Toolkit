"""Saved Auction House administration preset API."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .presets import PresetError, delete_preset, get_preset, list_presets, save_preset
from .rule_cleanup import criteria_from_payload, preview_cleanup
from .synthetic_seed import preview_synthetic_category_seed

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


@router.get(".json")
def presets_list(kind: str | None = Query(default=None)):
    try:
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
        config = dict(preset.get("config") or {})
        with _context() as ctx:
            if preset["kind"] == "cleanup":
                preview = preview_cleanup(ctx.service, criteria_from_payload(config))
            elif preset["kind"] == "synthetic_seed":
                preview = preview_synthetic_category_seed(
                    service=ctx.service,
                    category_id=int(config.get("category_id") or 0),
                    price=int(config.get("price") or 0),
                    stack_mode=str(config.get("stack_mode") or "single"),
                    copies_per_item=int(config.get("copies_per_item") or 1),
                    limit_items=int(config.get("limit_items") or 100),
                )
            else:
                raise PresetError("Unsupported Auction House preset kind")
        return JSONResponse({"preset": preset, "preview": preview})
    except (PresetError, LegacyTestExecutionBlocked) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
