"""Basic melee overview: page + JSON API. Read-only what-if."""
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
            c[k] = (v in (True, "true", "True", 1)) if isinstance(d, bool) else float(v) if isinstance(d, (int, float)) else str(v)
        except (TypeError, ValueError):
            pass
    if c["wtype"] not in ("auto", "1h", "2h", "h2h", "dw"):
        c["wtype"] = "auto"
    c["ench"] = int(c["ench"])
    return c


def _w(x):
    if not isinstance(x, dict):
        return None
    try:
        return dict(skill=int(x.get("skill") or 0), dmg=float(x.get("dmg") or 0), delay=float(x.get("delay") or 0), hit=int(x.get("hit") or 1))
    except (TypeError, ValueError):
        return None


def create_melee_router(templates) -> APIRouter:
    r = APIRouter()

    @r.get("/tools/melee-calc", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse(request, "melee_calc.html", {"request": request})

    @r.get("/api/melee-calc/meta")
    def meta():
        return JSONResponse({"defaults": M.DEFAULTS})

    @r.post("/api/melee-calc/compute")
    async def compute(request: Request):
        b = await request.json()
        g = {str(k): float(v) for k, v in (b.get("gear") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        return JSONResponse(M.compute(_cfg(b.get("cfg")), g, _w(b.get("weapon")), _w(b.get("sub"))))
    return r
