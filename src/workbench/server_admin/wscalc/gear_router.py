"""Gear loadout API shared by the weapon skill and magic calculators."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import gear as G
from . import presets as P


def _ctx():
    from workbench.editors.character.connection import connect_from_server_root
    from workbench.runtime import settings_store as S
    root = S.get_active_server_root()
    if not root:
        raise HTTPException(status_code=503, detail="No active server root configured")
    return root, connect_from_server_root(root)


def create_gear_router() -> APIRouter:
    r = APIRouter()
    cache: dict = {}

    @r.get("/api/gear/meta")
    def meta():
        root, conn = _ctx()
        conn.close()
        if str(root) not in cache:
            cache[str(root)] = G.augment_options(root)
        return JSONResponse({"slots": G.slots(), "augments": cache[str(root)], "labels": G.STAT_LABEL, "presets": P.load(), "jobs": G.JOBS, "races": G.RACES})

    @r.get("/api/gear/items")
    def items(slot: int, q: str = "", job: int = 0, level: int = 0):
        root, conn = _ctx()
        try:
            return JSONResponse({"items": G.search(conn, slot, q, job=job, level=level)})
        finally:
            conn.close()

    @r.post("/api/gear/totals")
    async def totals(request: Request):
        body = await request.json()
        root, conn = _ctx()
        try:
            return JSONResponse(G.totals(conn, root, body.get("loadout") or [], body.get("profile")))
        finally:
            conn.close()

    return r
