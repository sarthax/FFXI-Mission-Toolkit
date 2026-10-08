"""Opt-in, GET-only HTTP API for explicitly registered replay sessions.

No process discovery, telemetry ingestion, file loading or write endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from .registry import ReplayRegistry
from .viewer import viewer_projection


def create_registry_router(registry: ReplayRegistry) -> APIRouter:
    router = APIRouter(prefix="/live-client/replay", tags=["Live Client Replay"])

    @router.get("/clients")
    def clients() -> dict:
        return {"clients": list(registry.status())}

    @router.get("/projection")
    def projection(
        client_id: str = Query(min_length=1, max_length=200),
        zone_id: int = Query(ge=0, le=65535),
        instance_hint: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> dict:
        if client_id not in registry.client_ids():
            raise HTTPException(status_code=404, detail="replay client not registered")
        frame = registry.frame(client_id)
        if frame is None:
            raise HTTPException(status_code=409, detail="replay client has no observed frame")
        if frame.snapshot.client_id != client_id:
            raise HTTPException(status_code=409, detail="client identity mismatch")
        return viewer_projection(frame, zone_id=zone_id, client_id=client_id,
                                 instance_hint=instance_hint)

    @router.get("/trace")
    def trace(client_id: str = Query(min_length=1, max_length=200),
              max_points: int = Query(default=500, ge=1, le=1000)) -> dict:
        replay = registry._clients.get(client_id)
        if replay is None:
            raise HTTPException(status_code=404, detail="recorded client not registered")
        return {"client_id": client_id, "points": replay.path_points(max_points=max_points)}

    @router.post("/poll-feed")
    def poll_feed(request: Request, client_id: str = Query(min_length=1, max_length=200)) -> dict:
        """Read bounded frames from an explicitly registered local telemetry file."""
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")
        if client_id not in registry._feeds:
            raise HTTPException(status_code=404, detail="file feed not registered")
        try:
            count = registry.poll_feed(client_id)
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"client_id": client_id, "accepted": count}

    @router.post("/navigate")
    def navigate(request: Request, client_id: str = Query(min_length=1, max_length=200),
                 action: str = Query(pattern="^(restart|previous)$")) -> dict:
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")
        try:
            frame = registry.navigate(client_id, action)
        except KeyError:
            raise HTTPException(status_code=404, detail="replay client not registered")
        except (StopIteration, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error))
        return {"client_id": client_id, "observed_at": frame.snapshot.observed_at,
                "zone_id": frame.snapshot.position.zone_id}

    @router.post("/advance")
    def advance(request: Request, client_id: str = Query(min_length=1, max_length=200)) -> dict:
        """Advance offline replay only; reject browser cross-origin submissions."""
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")
        if client_id not in registry.client_ids():
            raise HTTPException(status_code=404, detail="replay client not registered")
        try:
            frame = registry.advance(client_id)
        except StopIteration:
            raise HTTPException(status_code=409, detail="end of recording")
        return {"client_id": client_id, "observed_at": frame.snapshot.observed_at,
                "zone_id": frame.snapshot.position.zone_id}

    return router
