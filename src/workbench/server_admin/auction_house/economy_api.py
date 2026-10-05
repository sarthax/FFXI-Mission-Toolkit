"""Read-only Auction House economy-intelligence API and page."""
from __future__ import annotations

from contextlib import contextmanager
import sys

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .economy_intelligence import economy_intelligence
from .factory import open_auction_house

router = APIRouter(tags=["Auction House Economy Intelligence"])
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


@router.get("/auction-house/economy", response_class=HTMLResponse)
def economy_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_economy.html",
        context={"title": "Auction House Economy Intelligence"},
    )


@router.get("/auction-house/economy.json")
def economy_json(
    days: int = Query(default=30, ge=1, le=3650),
    stale_days: int = Query(default=30, ge=1, le=3650),
    seller_id: int | None = Query(default=None, ge=1),
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    sample_limit: int = Query(default=20000, ge=100, le=50000),
):
    try:
        with _context() as ctx:
            return JSONResponse(economy_intelligence(
                ctx.service,
                days=days,
                stale_days=stale_days,
                seller_id=seller_id,
                category_id=category_id,
                limit=limit,
                sample_limit=sample_limit,
            ))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
