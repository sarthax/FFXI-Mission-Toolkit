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

    @router.post("/start")
    def start(request: Request) -> dict:
        require_same_origin(request)
        try:
            host, port = manager.start()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"running": True, "host": host, "port": port}

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
