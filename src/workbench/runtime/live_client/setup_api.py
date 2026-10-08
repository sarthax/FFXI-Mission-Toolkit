"""Same-origin local recording upload for Live Client Settings.

Uploaded files are validated before being retained in the toolkit's managed
recordings folder. Never executes content or attaches to game processes.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, UploadFile

from .inspection import inspect_recording
from .recording import load_recorded_frames
from .registry import ReplayRegistry

MAX_UPLOAD_BYTES = 16 * 1024 * 1024


def create_recording_upload_router(directory: Path, registry: ReplayRegistry | None = None) -> APIRouter:
    router = APIRouter(prefix="/live-client", tags=["Live Client Settings"])

    @router.post("/upload-recording")
    async def upload_recording(request: Request, recording: UploadFile, open_session: bool = False) -> dict:
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")
        if not recording.filename or not recording.filename.lower().endswith(".jsonl"):
            raise HTTPException(status_code=422, detail="select a .jsonl recording")
        data = await recording.read(MAX_UPLOAD_BYTES + 1)
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="recording must be 1 byte to 16 MiB")
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        output = destination / f"{uuid4().hex}.jsonl"
        try:
            with output.open("xb") as handle:
                handle.write(data)
            result = inspect_recording(str(output))
        except (ValueError, OSError) as exc:
            output.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc))
        if registry is not None and open_session:
            client_id = result["client_id"]
            if client_id in registry.client_ids():
                output.unlink(missing_ok=True)
                raise HTTPException(status_code=409, detail="client already loaded")
            try:
                replay = load_recorded_frames(output, client_id=client_id)
                replay.advance()
                registry.add(client_id, replay)
            except (ValueError, OSError) as exc:
                output.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail=str(exc))
        return {**result, "path": str(output), "loaded": registry is not None and open_session}

    return router
