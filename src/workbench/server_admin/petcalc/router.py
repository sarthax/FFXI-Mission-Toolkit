"""Pet gear overview: page + JSON API. Read-only what-if."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import model as M


def _cfg(raw):
    c = dict(M.DEFAULTS)
    for k, v in (raw or {}).items():
        if k not in c:
            continue
        d = M.DEFAULTS[k]
        try:
            c[k] = bool(v) if isinstance(d, bool) else float(v) if isinstance(d, (int, float)) else str(v)
        except (TypeError, ValueError):
            pass
    if c["kind"] not in M.KINDS:
        c["kind"] = "avatar"
    return c


def create_pet_router(templates) -> APIRouter:
    r = APIRouter()

    @r.get("/tools/pet-calc", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse(request, "pet_calc.html", {"request": request})

    @r.get("/api/pet-calc/meta")
    def meta():
        return JSONResponse({"defaults": M.DEFAULTS, "kinds": {k: v[0] for k, v in M.KINDS.items()}, "elements": list(M.AFFINITY)})

    @r.post("/api/pet-calc/compute")
    async def compute(request: Request):
        b = await request.json()
        c = _cfg(b.get("cfg"))
        pet = {str(t): {str(k): float(v) for k, v in d.items() if isinstance(v, (int, float))} for t, d in (b.get("pet") or {}).items() if isinstance(d, dict)}
        master = {str(k): float(v) for k, v in (b.get("master") or {}).items() if isinstance(v, (int, float))}
        return JSONResponse(M.compute(c, pet, master))
    return r
