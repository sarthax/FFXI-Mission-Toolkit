"""Optional read-only HTTP router for validated live-client viewer observations.

This router is deliberately NOT auto-registered with the application. The caller
must supply a trusted, already-decoded frame provider for a selected client.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query

from .telemetry import TelemetryFrame
from .viewer import viewer_projection


def create_readonly_router(frame_provider: Callable[[str], TelemetryFrame | None]) -> APIRouter:
    """Create GET-only endpoints; never expose raw telemetry ingest or writes."""
    router = APIRouter(prefix="/live-client/read-only", tags=["Live Client Read Only"])

    @router.get("/projection")
    def projection(
        client_id: str = Query(min_length=1, max_length=200),
        zone_id: int = Query(ge=0, le=65535),
        instance_hint: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> dict:
        frame = frame_provider(client_id)
        if frame is None:
            raise HTTPException(status_code=404, detail="no observation for selected client")
        if frame.snapshot.client_id != client_id:
            # Guard against a provider returning data for the wrong client.
            raise HTTPException(status_code=409, detail="client observation mismatch")
        return viewer_projection(
            frame, zone_id=zone_id, client_id=client_id,
            instance_hint=instance_hint,
        )

    return router
