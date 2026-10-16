"""Weapon skill damage calculator: page + JSON API. Read-only; edits are what-if overrides, never written to Lua."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import data as D
from . import model as M

DEFAULT_STATS = dict(lvl=90, str=180, dex=150, vit=120, agi=120, int=100, mnd=100, chr=100, att=1500, acc=1200,
                     wdmg=120, wdmg_rank=13, t_vit=100, t_agi=100, t_def=1300, t_eva=900, t_lvl=90,
                     matt=50, mdef=0, macc=900, meva=700, t_int=100, day_wx=0, crit_rate=10, crit_dmg=0, da=10, ta=5, qa=0, wsd=30, pdl=0, offhand=False,
                     ratt=1500, racc=1200, rdmg=100, rdmg_rank=11, hp=3000, max_hp=3000, max_mp=1500, club_skill=400)


KINDS = ("physical", "magical", "ranged", "special")


def _stats(raw: dict) -> dict:
    s = dict(DEFAULT_STATS)
    for k, v in (raw or {}).items():
        if k in s:
            s[k] = bool(v) if k == "offhand" else float(v)
    s["lvl"], s["t_lvl"] = int(s["lvl"]), int(s["t_lvl"])
    return s


def _merge(skill: dict, overrides: dict | None, adoulin: bool) -> dict:
    w = {**skill, "params": dict(skill["params"])}
    if adoulin:
        w["params"].update(skill["adoulin"])
    for k, v in (overrides or {}).items():
        if k in w["params"] or k in ("numHits", "multiHitfTP", "canCrit"):
            w["params"][k] = v if isinstance(v, bool) else float(v)
    return w


def create_wscalc_router(templates, get_dsp_root) -> APIRouter:
    r = APIRouter()

    def skills() -> dict:
        root = get_dsp_root()
        if not root:
            raise HTTPException(status_code=503, detail="DSP root is not configured in Settings")
        return D.load(root)

    @r.get("/tools/ws-calc", response_class=HTMLResponse)
    def page(request: Request):
        return templates.TemplateResponse(request, "ws_calc.html", {"request": request})

    @r.get("/api/ws-calc/skills")
    def api_skills():
        s = skills()
        return JSONResponse({"defaults": DEFAULT_STATS, "skills": [
            {"name": k, "kind": v["kind"], "weapon": v["weapon"], "params": v["params"], "adoulin": v["adoulin"],
             "conditionals": v["conditionals"]} for k, v in s.items() if v["kind"] in KINDS and ("ftp100" in v["params"] or v["kind"] == "special")]})

    @r.post("/api/ws-calc/compute")
    async def api_compute(request: Request):
        body = await request.json()
        s = skills().get(body.get("skill"))
        if not s:
            raise HTTPException(status_code=404, detail="unknown skill")
        stats, tp, ado = _stats(body.get("stats")), int(body.get("tp", 3000)), bool(body.get("adoulin"))
        orig, edited = _merge(s, None, ado), _merge(s, body.get("overrides"), ado)
        if s["kind"] == "special":
            f = lambda tt: M.compute_special(s["name"], stats, tt, ado)
            return JSONResponse({"kind": "special", "dsp": {"edited": f(tp), "original": f(tp)},
                                 "tp_curve": [{"tp": t, "dsp": f(t)["total"]} for t in (1000, 1500, 2000, 2500, 3000)]})
        if s["kind"] == "ranged":
            r_o, r_e = M.compute_ranged(orig, stats, tp), M.compute_ranged(edited, stats, tp)
            return JSONResponse({"kind": "ranged", "dsp": {"original": r_o, "edited": r_e},
                                 "tp_curve": [{"tp": t, "dsp": M.compute_ranged(edited, stats, t)["total"]} for t in (1000, 1500, 2000, 2500, 3000)]})
        if s["kind"] == "magical":
            r_o, r_e = M.compute_magic(orig, stats, tp), M.compute_magic(edited, stats, tp)
            return JSONResponse({"kind": "magical", "dsp": {"original": r_o, "edited": r_e},
                                 "tp_curve": [{"tp": t, "dsp": M.compute_magic(edited, stats, t)["total"]} for t in (1000, 1500, 2000, 2500, 3000)]})
        out = {}
        for mode in ("dsp", "retail"):
            out[mode] = {"original": M.compute(orig, stats, mode, tp), "edited": M.compute(edited, stats, mode, tp)}
        out["tp_curve"] = [{"tp": t, "dsp": M.compute(edited, stats, "dsp", t)["total"],
                            "retail": M.compute(edited, stats, "retail", t)["total"]} for t in (1000, 1500, 2000, 2500, 3000)]
        return JSONResponse(out)

    @r.post("/api/ws-calc/compare")
    async def api_compare(request: Request):
        body = await request.json()
        stats, tp, ado = _stats(body.get("stats")), int(body.get("tp", 3000)), bool(body.get("adoulin"))
        weapon = body.get("weapon")
        rows = []
        for k, v in skills().items():
            if v["kind"] not in KINDS or ("ftp100" not in v["params"] and v["kind"] != "special") or (weapon and v["weapon"] != weapon):
                continue
            w = _merge(v, None, ado)
            if v["kind"] == "special":
                rows.append({"name": k, "weapon": v["weapon"], "dsp": round(M.compute_special(k, stats, tp, ado)["total"]), "retail": None, "special": True})
                continue
            if v["kind"] == "ranged":
                rows.append({"name": k, "weapon": v["weapon"], "dsp": round(M.compute_ranged(w, stats, tp)["total"]), "retail": None, "special": bool(v["conditionals"])})
                continue
            if v["kind"] == "magical":
                rows.append({"name": k, "weapon": v["weapon"], "dsp": round(M.compute_magic(w, stats, tp)["total"]),
                             "retail": None, "special": bool(v["conditionals"]), "magical": True})
                continue
            rows.append({"name": k, "weapon": v["weapon"], "dsp": round(M.compute(w, stats, "dsp", tp)["total"]),
                         "retail": round(M.compute(w, stats, "retail", tp)["total"]), "special": bool(v["conditionals"])})
        rows.sort(key=lambda x: -x["dsp"])
        return JSONResponse({"rows": rows})

    return r
