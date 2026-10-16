"""Healing / defense overview: page + JSON API. Read-only what-if."""
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
    return c


def create_heal_router(templates) -> APIRouter:
    r = APIRouter()

    @r.get("/tools/heal-calc", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse(request, "heal_calc.html", {"request": request})

    @r.get("/api/heal-calc/meta")
    def meta():
        return JSONResponse({"defaults": M.DEFAULTS, "elements": M.EL, "statuses": M.STATUS})

    @r.post("/api/heal-calc/compute")
    async def compute(request: Request):
        b = await request.json()
        c = _cfg(b.get("cfg"))
        m = {str(k): float(v) for k, v in (b.get("mods") or {}).items() if isinstance(v, (int, float))}
        tk, hints = M.taken(m)
        return JSONResponse({"cure_power": M.cure_power(c), "cure_power_old": M.cure_power(c, True), "daywx": M.day_weather(c),
                             "heals": M.heals(c, m), "taken": tk, "hints": hints, "defense": M.defense(c, m), "resists": M.resists(c, m)})
    return r
