"""Rule-driven Auction House cleanup API and page."""
from __future__ import annotations

from contextlib import contextmanager
import sys

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .activity import record_executor_result
from .factory import open_auction_house
from .legacy_test_executor import LegacyTestExecutionBlocked
from .rule_cleanup import criteria_from_payload, execute_cleanup, preview_cleanup

router = APIRouter(tags=["Auction House Cleanup"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))


def _sync_host_template_globals() -> None:
    for module_name in ("gui_server", "__main__"):
        host = sys.modules.get(module_name)
        host_templates = getattr(host, "templates", None) if host is not None else None
        host_env = getattr(host_templates, "env", None)
        host_globals = getattr(host_env, "globals", None)
        if host_globals:
            templates.env.globals.update(host_globals)
            return


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


@router.get("/auction-house/cleanup", response_class=HTMLResponse)
def cleanup_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_cleanup.html",
        context={"title": "Auction House Cleanup"},
    )


@router.post("/auction-house/cleanup/preview.json")
def cleanup_preview(payload: dict = Body(default={})):
    try:
        criteria = criteria_from_payload(payload)
        with _context() as ctx:
            return JSONResponse(preview_cleanup(ctx.service, criteria))
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/auction-house/test-write/cleanup.json")
def cleanup_execute(payload: dict = Body(...)):
    try:
        criteria = criteria_from_payload(dict(payload.get("criteria") or {}))
        token = str(payload.get("preview_token") or "")
        action = str(payload.get("action") or "")
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            result = execute_cleanup(
                service=ctx.service,
                environment=environment,
                criteria=criteria,
                preview_token=token,
                action=action,
                confirmation=confirmation,
            )
        try:
            record_executor_result(
                environment=environment,
                result=result,
                request_payload=payload,
                operation=f"cleanup_{action or 'unknown'}",
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
