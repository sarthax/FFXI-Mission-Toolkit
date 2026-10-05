"""Unified Auction House administration activity API and page."""
from __future__ import annotations

import sys

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.paths import GUI_ROOT

from .activity import unified_activity

router = APIRouter(tags=["Auction House Activity"])
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


@router.get("/auction-house/activity", response_class=HTMLResponse)
def activity_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_activity.html",
        context={"title": "Auction House Activity"},
    )


@router.get("/auction-house/activity.json")
def activity_json(
    environment_name: str | None = None,
    operation: str | None = None,
    status: str | None = None,
    character_id: int | None = Query(default=None, ge=1),
    item_id: int | None = Query(default=None, ge=1),
    since_utc: str | None = None,
    until_utc: str | None = None,
    include_evidence: bool = True,
    include_campaigns: bool = True,
    limit: int = Query(default=200, ge=1, le=1000),
):
    try:
        return JSONResponse(unified_activity(
            environment_name=environment_name,
            operation=operation,
            status=status,
            character_id=character_id,
            item_id=item_id,
            since_utc=since_utc,
            until_utc=until_utc,
            include_evidence=include_evidence,
            include_campaigns=include_campaigns,
            limit=limit,
        ))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
