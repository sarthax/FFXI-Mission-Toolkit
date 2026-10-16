"""Magic nuke calculators (elemental + ninjutsu): page + JSON API. Read-only what-if."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import magic_model as M


def _cfg(raw: dict) -> dict:
    c = dict(M.DEFAULTS)
    for k, v in (raw or {}).items():
        if k not in c:
            continue
        d = M.DEFAULTS[k]
        if k == 'aff_gear':
            c[k] = {str(a): float(b) for a, b in (v or {}).items()}
        elif k == 't_int':
            c[k] = None if v in (None, '') else float(v)
        elif isinstance(d, bool):
            c[k] = bool(v)
        elif isinstance(d, (int, float)):
            c[k] = float(v)
        else:
            c[k] = str(v)
    for k in ('lvl', 't_lvl', 'burst_step', 'C', 'F', 'G'):
        c[k] = int(c[k])
    return c


def create_magic_router(templates) -> APIRouter:
    r = APIRouter()

    @r.get("/tools/magic-calc", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse(request, "magic_calc.html", {"request": request})

    @r.get("/api/magic-calc/meta")
    def meta():
        return JSONResponse({"defaults": M.DEFAULTS, "elements": M.E8, "mixes": M.MIXES,
                             "nuke": [{"name": k, "element": v["element"], "cls": v["cls"], "tier": v["tier"]} for k, v in M.NUKES.items()],
                             "nin": [{"name": k, "element": v["element"], "cls": "Ninjutsu", "tier": v["tier"]} for k, v in M.NINS.items()],
                             "mobs": [{"family": k, "int": v["int"]} for k, v in M.MOBS.items()]})

    @r.post("/api/magic-calc/compute")
    async def compute(request: Request):
        b = await request.json()
        kind, spell = b.get("kind"), b.get("spell")
        c = _cfg(b.get("cfg"))
        table = M.NUKES if kind == "nuke" else M.NINS if kind == "nin" else None
        if table is None or spell not in table:
            raise HTTPException(status_code=404, detail="unknown spell")
        fn = M.calc_nuke if kind == "nuke" else M.calc_nin
        mob = M.MOBS.get(b.get("family"))
        mix = (c["C"], c["F"], c["G"])
        mixes = [("Your mix",) + mix] + list(M.MIXES)
        rows = []
        for m in mixes:
            x = fn(spell, c, m[1:], mob)
            x["mix"] = m[0]
            x["pieces"] = list(m[1:])
            rows.append(x)
        comp = sorted((fn(k, c, mix, mob) for k in table), key=lambda x: -x["final"])
        out = {"rows": rows, "compare": comp}
        if kind == "nin":
            out["chain"] = {p: {k: fn(k, {**c, "prev": p}, mix, mob)["final"] for k in table if k.endswith("_" + b.get("chain_tier", "san"))}
                            for p in ["None"] + M.E8[:6]}
        return JSONResponse(out)

    return r
