"""Auction House Seeder operator page."""
from __future__ import annotations

import sys

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.paths import GUI_ROOT

router = APIRouter(tags=["Auction House Seeder"])
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


@router.get("/auction-house/seeder", response_class=HTMLResponse)
def auction_house_seeder_page(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_seeder.html",
        context={"title": "Auction House Seeder"},
    )
