"""Opt-in same-origin read-only Live Client bridge setup and status routes.

Routes are not auto-registered: the Toolkit application must deliberately mount
them. Provisioning reveals a local secret only in the direct POST response.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query
from .viewer import viewer_projection
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .bridge_managed import ManagedLiveReceiver
from .bridge_settings_file import render_settings_lua, write_settings
from .ashita_install import (preview as preview_ashita_addon, install_missing as install_ashita_addon,
                             preview_upgrade as preview_ashita_upgrade, upgrade_with_backup as apply_ashita_upgrade)


class AshitaInstallSelection(BaseModel):
    ashita_root: str = Field(min_length=1, max_length=2048)


class AshitaInstallConfirmation(AshitaInstallSelection):
    expected: dict


class QuickStart(BaseModel):
    client_id: str = Field(default="ashita-a", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ashita_root: str | None = Field(default=None, max_length=2048)
    regenerate: bool = False


class ClientSelection(BaseModel):
    client_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


def create_bridge_management_router(manager: ManagedLiveReceiver, templates: Jinja2Templates | None = None) -> APIRouter:
    if templates is None:
        templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[4] / "gui" / "templates"))
        templates.env.globals["current_theme"] = lambda: "light"
        templates.env.globals["shell_context"] = lambda _request: {
            "workspaces": [], "sections": [], "active_home": False,
            "snapshot_context": [], "brand": {"enabled": False}
        }
    router = APIRouter(prefix="/live-client/bridge", tags=["Live Client Bridge"])

    def require_same_origin(request: Request) -> None:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="bridge control requires local browser")
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")

    @router.get("/console", response_class=HTMLResponse)
    def console(request: Request) -> HTMLResponse:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="bridge setup requires local browser")
        return templates.TemplateResponse(request, "live_client_bridge.html")

    @router.post("/installer/preview")
    def installer_preview(request: Request, selection: AshitaInstallSelection) -> dict:
        require_same_origin(request)
        try:
            return preview_ashita_addon(selection.ashita_root)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/installer/apply")
    def installer_apply(request: Request, selection: AshitaInstallConfirmation) -> dict:
        require_same_origin(request)
        try:
            return install_ashita_addon(selection.ashita_root, selection.expected)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/installer/upgrade-preview")
    def installer_upgrade_preview(request: Request, selection: AshitaInstallSelection) -> dict:
        require_same_origin(request)
        try:
            return preview_ashita_upgrade(selection.ashita_root)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/installer/upgrade-apply")
    def installer_upgrade_apply(request: Request, selection: AshitaInstallConfirmation) -> dict:
        require_same_origin(request)
        try:
            return apply_ashita_upgrade(selection.ashita_root, selection.expected)
        except (ValueError, OSError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/start")
    def start(request: Request) -> dict:
        require_same_origin(request)
        try:
            host, port = manager.start()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"running": True, "host": host, "port": port}

    @router.get("/state")
    def remembered_state(request: Request) -> dict:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="bridge setup requires local browser")
        return {"running": manager.running, "ashita_root": manager.remembered_ashita_root(),
                "clients": manager.clients()}

    @router.post("/quick-start")
    def quick_start(request: Request, selection: QuickStart) -> dict:
        """One step: start receiver (idempotent), reuse/issue credentials, write Ashita settings."""
        require_same_origin(request)
        try:
            if not manager.running:
                manager.start()
            creds = manager.provision(selection.client_id, reuse=not selection.regenerate)
            root = selection.ashita_root or manager.remembered_ashita_root()
            result = {"running": True, "host": creds["host"], "port": creds["port"],
                      "client_id": selection.client_id, "settings_written": False,
                      "settings_changed": False, "command": "/wblive live start " + selection.client_id}
            if root:
                try:
                    path, changed = write_settings(root, creds)
                except (ValueError, OSError) as exc:
                    result["settings_error"] = str(exc)
                else:
                    manager.remember_ashita_root(root)
                    result.update(settings_written=True, settings_changed=changed, settings_path=str(path))
            if not result["settings_written"]:
                # No usable Ashita folder: hand the file back for manual download.
                result["settings_lua"] = render_settings_lua(creds)
            return result
        except (RuntimeError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/reset-credentials")
    def reset_credentials(request: Request, selection: ClientSelection) -> dict:
        require_same_origin(request)
        manager.reset_credentials(selection.client_id)
        return {"reset": selection.client_id}

    @router.post("/provision")
    def provision(request: Request, selection: ClientSelection) -> dict:
        require_same_origin(request)
        try:
            return manager.provision(selection.client_id)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/clients")
    def clients() -> dict:
        return {"clients": manager.clients()}

    @router.get("/projection")
    def projection(
        client_id: str = Query(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
        zone_id: int = Query(ge=1, le=65535),
        instance_hint: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> dict:
        """Live-only spatial projection; never show stale or wrong-zone markers."""
        state = manager.status(client_id)
        if not state["connected"]:
            return {"visible": False, "player": None, "entities": [],
                    "reason": "receiver_disconnected_or_stale"}
        feed = manager.feeds.feed(client_id)
        frame = feed._latest if feed else None
        if frame is None:
            return {"visible": False, "player": None, "entities": [],
                    "reason": "no_live_observation"}
        return viewer_projection(
            frame, zone_id=zone_id, client_id=client_id,
            instance_hint=instance_hint,
        )

    @router.get("/status/{client_id}")
    def status(client_id: str) -> dict:
        if not 0 < len(client_id) <= 64 or not client_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=422, detail="invalid client ID")
        result = manager.status(client_id)
        snapshot = result.pop("snapshot", None)
        frame = manager.feeds.feed(client_id)
        frame = frame._latest if frame else None
        if snapshot is None:
            result["snapshot"] = None
        else:
            pos = snapshot.position
            result["snapshot"] = {
                "client_id": snapshot.client_id, "character": snapshot.character,
                "client_version": snapshot.version, "adapter": snapshot.adapter,
                "observed_at": snapshot.observed_at,
                "zone_id": pos.zone_id, "x": pos.x, "y": pos.y, "z": pos.z,
                "heading": pos.heading,
                "entities": [
                    {"client_index": entity.client_index, "name": entity.name,
                     "kind": entity.kind,
                     "zone_id": entity.position.zone_id,
                     "x": entity.position.x, "y": entity.position.y,
                     "z": entity.position.z}
                    for entity in (frame.entities if frame else ())
                ],
            }
        return result

    @router.post("/stop")
    def stop(request: Request) -> dict:
        require_same_origin(request)
        manager.stop()
        return {"running": False}

    return router
