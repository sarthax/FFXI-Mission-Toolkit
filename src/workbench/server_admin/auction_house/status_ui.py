"""Shared Auction House status/readiness and help surfaces."""
from __future__ import annotations

import sys
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .factory import open_auction_house
from .legacy_test_executor import evaluate_legacy_test_write_gate
from .player_listing import probe_player_listing_engines
from .player_purchase import probe_player_purchase_engines

router = APIRouter(tags=["Auction House Status"])
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


@router.get("/auction-house/status.json")
def auction_house_status():
    environment = get_active_server_identity() or {}
    root = get_active_server_root()
    if root is None:
        return JSONResponse({
            "configured": False,
            "scoped_test_write_ready": False,
            "read_only_ready": False,
            "blockers": ["No active server environment is configured."],
        })

    try:
        ctx = open_auction_house(root)
        try:
            profile_name = str(environment.get("name") or "")
            gate = evaluate_legacy_test_write_gate(
                environment=environment,
                schema_family_hint=ctx.service.schema.family_hint,
                confirmation=profile_name,
            )
            listing_probe = probe_player_listing_engines(ctx.service.connection)
            purchase_probe = probe_player_purchase_engines(ctx.service.connection)
            blockers = [issue.message for issue in gate.issues if issue.blocking]
            return JSONResponse({
                "configured": True,
                "environment": environment,
                "schema_family": ctx.service.schema.family_hint,
                "read_only_ready": True,
                "scoped_test_write_ready": bool(gate.ready),
                "write_gate": gate.as_dict(),
                "player_listing_transactional": bool(listing_probe.transactional),
                "player_purchase_transactional": bool(purchase_probe.transactional),
                "listing_engine_probe": listing_probe.as_dict(),
                "purchase_engine_probe": purchase_probe.as_dict(),
                "blockers": blockers,
                "capability_note": (
                    "Scoped DSP/Topaz Test executors are available when the Test gate passes. "
                    "This does not enable unrestricted or Live writes."
                ),
            })
        finally:
            ctx.close()
    except Exception as exc:
        return JSONResponse({
            "configured": True,
            "environment": environment,
            "read_only_ready": False,
            "scoped_test_write_ready": False,
            "blockers": [str(exc)],
        }, status_code=503)


@router.get("/auction-house/help", response_class=HTMLResponse)
def auction_house_help(request: Request):
    _sync_host_template_globals()
    return templates.TemplateResponse(
        request=request,
        name="auction_house_help.html",
        context={"title": "Auction House Help & Status"},
    )
