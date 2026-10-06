"""Synth & Crafting routes: page, read-only recipe/availability endpoints, SQL preview/export, gated Test-environment save."""
from __future__ import annotations

import sys
from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.runtime.paths import GUI_ROOT
from workbench.server_admin.auction_house.factory import open_auction_house
from workbench.server_admin.auction_house.legacy_test_executor import evaluate_legacy_test_write_gate

from . import recipes as R

router = APIRouter(tags=["Synth & Crafting"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))


@contextmanager
def _ctx():
    root = get_active_server_root()
    if root is None:
        raise HTTPException(status_code=503, detail="No active DSP/Topaz/LSB server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield ctx, root
    finally:
        ctx.close()


def _guard(fn):
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/synth", response_class=HTMLResponse)
def synth_page(request: Request):
    for name in ("gui_server", "__main__"):
        env = getattr(getattr(sys.modules.get(name), "templates", None), "env", None)
        if getattr(env, "globals", None):
            templates.env.globals.update(env.globals)
            break
    return templates.TemplateResponse(request=request, name="synth.html", context={"title": "Synth & Crafting"})


@router.get("/synth/recipes.json")
def recipes_json(craft: str = "", min_skill: int = Query(0, ge=0, le=255), max_skill: int = Query(255, ge=0, le=255), q: str = "",
                 mode: str = "synth", item_id: int = Query(0, ge=0), role: str = "any",
                 limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), with_status: int = 0):
    def go():
        with _ctx() as (ctx, root):
            return JSONResponse(R.list_recipes(ctx.service.connection, craft=craft, min_skill=min_skill, max_skill=max_skill, q=q,
                                               mode=mode, item_id=item_id, role=role, limit=limit, offset=offset,
                                               with_status=bool(with_status), root=root))
    return _guard(go)


@router.get("/synth/recipe.json")
def recipe_json(id: int = Query(..., ge=0)):
    def go():
        with _ctx() as (ctx, _root):
            rc = R.get_recipe(ctx.service.connection, id)
            if rc is None:
                raise HTTPException(status_code=404, detail=f"Recipe {id} not found")
            return JSONResponse(rc)
    return _guard(go)


@router.get("/synth/check.json")
def check_json(id: int = Query(..., ge=0)):
    def go():
        with _ctx() as (ctx, root):
            res = R.check_recipe(ctx.service.connection, root, id)
            if res is None:
                raise HTTPException(status_code=404, detail=f"Recipe {id} not found")
            return JSONResponse(res)
    return _guard(go)


@router.get("/synth/audit.json")
def audit_json(mode: str = "synth", limit: int = Query(300, ge=1, le=2000)):
    def go():
        with _ctx() as (ctx, root):
            return JSONResponse(R.audit(ctx.service.connection, root, limit=limit, mode=mode))
    return _guard(go)


@router.get("/synth/items.json")
def items_json(q: str = Query("", max_length=60), limit: int = Query(25, ge=1, le=60)):
    """Item picker search (names and numeric ids). Ids shown are the live item_basic ids."""
    def go():
        with _ctx() as (ctx, _root):
            s = q.strip()
            if not s:
                return JSONResponse({"items": []})
            if s.isdigit():
                rows = R._rows(ctx.service.connection, "SELECT itemid,name FROM item_basic WHERE itemid=%s", (int(s),))
            else:
                like = "%" + s.replace(" ", "_") + "%"
                rows = R._rows(ctx.service.connection, "SELECT itemid,name FROM item_basic WHERE name LIKE %s OR sortname LIKE %s ORDER BY name LIMIT %s", (like, like, limit))
            return JSONResponse({"items": [{"item_id": int(r[0]), "name": str(r[1] or "")} for r in rows]})
    return _guard(go)


@router.post("/synth/preview.json")
def preview(payload: dict = Body(...)):
    """Validate a create/update/delete and return the exact SQL for every server flavor. Performs no write."""
    mode = str(payload.get("mode") or "create")
    if mode not in ("create", "update", "delete"):
        raise HTTPException(status_code=400, detail="mode must be create, update or delete")

    def go():
        with _ctx() as (ctx, _root):
            conn = ctx.service.connection
            if mode == "delete":
                rid = int(payload.get("id") or 0)
                rc = R.get_recipe(conn, rid)
                if rc is None:
                    return JSONResponse({"ok": False, "errors": [f"Recipe {rid} does not exist"], "warnings": [], "sql": {}})
                rec = {"id": rid, "comment": payload.get("comment")}
                return JSONResponse({"ok": True, "errors": [], "warnings": [f"Deletes recipe {rid} ({rc['name']})."],
                                     "recipe": rc, "sql": {f: R.build_sql(rec, f, "delete") for f in R.FLAVORS}, "active_flavor": R.detect_flavor(R.table_columns(conn))})
            rec, errors, warnings = R.validate(conn, payload.get("recipe") or {}, creating=(mode == "create"))
            flavor = R.detect_flavor(R.table_columns(conn))
            if "KeyItem" in R.table_columns(conn) and rec["key_item"]:
                warnings.append("Key item ids differ between DSP, Topaz and LSB — verify with id_bridge before porting.")
            return JSONResponse({"ok": not errors, "errors": errors, "warnings": warnings, "recipe": rec, "active_flavor": flavor,
                                 "sql": {f: R.build_sql(rec, f, mode) for f in R.FLAVORS} if not errors else {}})
    return _guard(go)


@router.post("/synth/export.json")
def export(payload: dict = Body(...)):
    """INSERT statements for chosen recipes in a chosen flavor (for porting between DSP/Topaz/LSB). Read only."""
    flavor = str(payload.get("flavor") or "dsp")
    if flavor not in R.FLAVORS:
        raise HTTPException(status_code=400, detail="flavor must be dsp, topaz or lsb")
    ids = [int(i) for i in (payload.get("ids") or [])][:500]

    def go():
        with _ctx() as (ctx, _root):
            lines, warnings = [], []
            for rid in ids:
                rc = R.get_recipe(ctx.service.connection, rid)
                if rc is None:
                    warnings.append(f"Recipe {rid} not found"); continue
                lines.append(R.build_sql(rc, flavor, "create"))
                if rc["key_item"]:
                    warnings.append(f"Recipe {rid} uses key item {rc['key_item']}: ids drift between servers, verify before porting")
            warnings.append("Item ids and recipe IDs are copied as-is from the active server; check they match the target server's item_basic.")
            return JSONResponse({"flavor": flavor, "sql": "\n".join(lines), "count": len(lines), "warnings": warnings})
    return _guard(go)


@router.post("/synth/save.json")
def save(payload: dict = Body(...)):
    """Apply one create/update/delete to the ACTIVE environment. Gated exactly like the AH Test writes."""
    mode = str(payload.get("mode") or "create")
    if mode not in ("create", "update", "delete"):
        raise HTTPException(status_code=400, detail="mode must be create, update or delete")
    environment = get_active_server_identity()

    def go():
        with _ctx() as (ctx, _root):
            conn = ctx.service.connection
            gate = evaluate_legacy_test_write_gate(environment=environment, schema_family_hint=ctx.service.schema.family_hint,
                                                   confirmation=str(payload.get("confirmation") or ""), feature_enabled=None)
            if not gate.ready:
                codes = ", ".join(i.code for i in gate.issues if i.blocking)
                raise HTTPException(status_code=409, detail=f"Recipe write blocked: {codes}")
            if mode == "delete":
                rid = int(payload.get("id") or 0)
                if R.get_recipe(conn, rid) is None:
                    raise HTTPException(status_code=404, detail=f"Recipe {rid} not found")
                rec = {"id": rid, "comment": payload.get("comment")}
            else:
                rec, errors, _w = R.validate(conn, payload.get("recipe") or {}, creating=(mode == "create"))
                if errors:
                    raise HTTPException(status_code=400, detail="; ".join(errors))
            before = R.get_recipe(conn, rec["id"]) if mode != "create" else None
            n = R.apply_recipe(conn, rec, mode)
            return JSONResponse({"ok": True, "mode": mode, "id": rec["id"], "rows": n, "before": before,
                                 "sql": R.build_sql(rec, R.detect_flavor(R.table_columns(conn)), mode)})
    return _guard(go)


# ---------------------------------------------------------------- analysis (read only)
import re as _re
from pathlib import Path as _Path

from fastapi.responses import PlainTextResponse

from . import analysis as A


@router.get("/synth/keyitems.json")
def keyitems_json():
    """Key items actually used by synth recipes, named from the active server's own keyitems.lua (ids drift between servers)."""
    def go():
        with _ctx() as (ctx, root):
            conn = ctx.service.connection
            names: dict[int, str] = {}
            lua = _Path(root) / "scripts" / "globals" / "keyitems.lua"
            if not lua.is_file():
                lua = next(iter((_Path(root) / "scripts").rglob("keyitems.lua")), lua)
            if lua.is_file():
                for m in _re.finditer(r"^\s*(?:tpz\.ki\.)?([A-Z0-9_]+)\s*=\s*(\d+)\s*[;,]?", lua.read_text(encoding="utf-8", errors="ignore"), _re.M):
                    names.setdefault(int(m.group(2)), m.group(1).replace("_", " ").title())
            used: dict[int, dict] = {}
            for rc in A.load_all(conn):
                if rc["key_item"]:
                    e = used.setdefault(rc["key_item"], {"count": 0, "crafts": {}})
                    e["count"] += 1
                    for c, lv in rc["skills"].items():
                        if lv:
                            e["crafts"][c] = e["crafts"].get(c, 0) + 1
            lo, hi = (min(used), max(used)) if used else (0, -1)
            block = sorted(set(used) | {k for k in names if lo <= k <= hi})
            def craft_of(k):
                if k in used and used[k]["crafts"]:
                    return max(used[k]["crafts"], key=used[k]["crafts"].get)
                near = [u for u in sorted(used) if abs(u - k) <= 8 and used[u]["crafts"]]
                if near:
                    u = min(near, key=lambda x: abs(x - k))
                    return max(used[u]["crafts"], key=used[u]["crafts"].get)
                return ""
            out = [{"id": k, "name": names.get(k, ""), "count": used[k]["count"] if k in used else 0, "craft": craft_of(k)} for k in block]
            return JSONResponse({"keyitems": out, "source": str(lua) if lua.is_file() else "", "note": "Every key item in the id range used by synth recipes, named from this server's keyitems.lua. Count 0 = not used by any recipe yet."})
    return _guard(go)


@router.get("/synth/profiles.json")
def profiles_json():
    from workbench.runtime.legacy_settings import get_server_profiles
    ident = get_active_server_identity()
    rows = [{"profile_id": p.profile_id, "name": p.name, "environment": p.environment, "family": p.family, "active": p.profile_id == ident.get("profile_id")}
            for p in get_server_profiles(include_disabled=False)]
    return JSONResponse({"profiles": rows, "active": ident.get("profile_id")})


def _other_root(profile_id: int):
    from workbench.runtime.legacy_settings import get_server_profiles
    for p in get_server_profiles(include_disabled=False):
        if p.profile_id == profile_id:
            return p
    raise HTTPException(status_code=404, detail="Unknown profile")


@router.get("/synth/compare.json")
def compare_json(other: int = Query(..., ge=0), limit: int = Query(300, ge=1, le=1000)):
    def go():
        prof = _other_root(other)
        with _ctx() as (ctx, _root):
            ident = get_active_server_identity()
            ctx_b = open_auction_house(prof.root_path)
            try:
                return JSONResponse(A.compare(ctx.service.connection, ctx_b.service.connection, ident.get("name") or "active", prof.name, limit))
            finally:
                ctx_b.close()
    return _guard(go)


@router.post("/synth/compare-sql.json")
def compare_sql(payload: dict = Body(...)):
    """INSERTs (in the target's layout) for recipes that exist in the chosen side. direction 'a2b' reads from the active server."""
    flavor = str(payload.get("flavor") or "dsp")
    if flavor not in R.FLAVORS:
        raise HTTPException(status_code=400, detail="flavor must be dsp, topaz or lsb")
    ids = [int(i) for i in (payload.get("ids") or [])][:1000]

    def go():
        src_other = payload.get("source_profile")
        with _ctx() as (ctx, _root):
            if src_other:
                prof = _other_root(int(src_other))
                c2 = open_auction_house(prof.root_path)
                try:
                    sql = A.sync_sql(c2.service.connection, ids, flavor)
                finally:
                    c2.close()
            else:
                sql = A.sync_sql(ctx.service.connection, ids, flavor)
            return JSONResponse({"sql": sql, "count": len([l for l in sql.splitlines() if l.strip()]),
                                 "warnings": ["Recipe ids are copied as-is. If the target already uses an id, change it or the INSERT will fail on the primary key.",
                                              "Key item ids differ between servers: check any recipe with a KeyItem before running."]})
    return _guard(go)


@router.get("/synth/economy.json")
def economy_json(limit: int = Query(300, ge=1, le=1000)):
    def go():
        with _ctx() as (ctx, root):
            return JSONResponse(A.economy(ctx.service.connection, root, limit=limit))
    return _guard(go)


@router.get("/synth/health.json")
def health_json():
    def go():
        with _ctx() as (ctx, root):
            return JSONResponse(A.health(ctx.service.connection, root))
    return _guard(go)


@router.get("/synth/audit.csv")
def audit_csv(mode: str = "synth"):
    def go():
        with _ctx() as (ctx, root):
            return PlainTextResponse(A.audit_csv(ctx.service.connection, root, mode), headers={"Content-Disposition": "attachment; filename=synth_audit.csv"}, media_type="text/csv")
    return _guard(go)


@router.get("/synth/item.json")
def item_json(id: int = Query(..., ge=1)):
    """Everything the editor shows when an item is clicked: basics, where it comes from, what makes it, where it is used."""
    def go():
        with _ctx() as (ctx, root):
            conn = ctx.service.connection
            rows = R._rows(conn, "SELECT name, stackSize, BaseSell, NoSale FROM item_basic WHERE itemid=%s", (id,))
            if not rows:
                raise HTTPException(status_code=404, detail=f"Item {id} is not in item_basic")
            name, stack, sell, nosale = rows[0]
            av = R.Availability(conn, root)
            d = av.direct(id)
            zones = {}
            try:
                zones = {int(z[0]): str(z[1]) for z in R._rows(conn, "SELECT zoneid, name FROM zone_settings")}
            except Exception:
                pass
            if d["drops"]:
                for s in d["drops"]["sample"]:
                    s["zone"] = zones.get(s["zone_id"], "")
            cols = R.table_columns(conn)
            ing_where = " OR ".join(f"`{c}`=%s" for c in R.INGREDIENTS)
            used = R._rows(conn, f"SELECT COUNT(*) FROM `synth_recipes` WHERE {ing_where} OR `Crystal`=%s", tuple([id] * 9))[0][0]
            made = [R.get_recipe(conn, rid) for rid in d["recipes"][:5]]
            return JSONResponse({"item_id": id, "name": str(name or ""), "stack": int(stack or 0), "sell": int(sell or 0), "nosale": bool(nosale),
                                 "status": av.status(id), "vendor": d["vendor"], "drops": d["drops"], "orphan_drop": d["orphan_drop"], "bcnm": d["bcnm"],
                                 "engine": d["engine"], "scripts": d["scripts"], "ah": d["ah"],
                                 "made_by": [{"id": m["id"], "craft": ", ".join(f"{k} {v}" for k, v in m["skills"].items() if v)} for m in made if m],
                                 "used_in": int(used)})
    return _guard(go)


@router.post("/synth/live.json")
def live_json(payload: dict = Body(...)):
    """Live analysis of the recipe being edited: validation, ingredient sourcing, duplicates, alternative recipes, rough cost. Read-only."""
    def go():
        with _ctx() as (ctx, root):
            conn = ctx.service.connection
            editing = int(payload.get("editing") or 0)
            rec, errors, warnings = R.validate(conn, payload.get("recipe") or {}, creating=not editing)
            av = R.Availability(conn, root)
            names = R.item_names(conn, {i for i in [*rec["ingredients"], rec["crystal"], *[x["item_id"] for x in rec["results"]]] if i})
            cost, unpriced, ings = 0, 0, []
            for iid in dict.fromkeys(rec["ingredients"]):
                d = av.direct(iid)
                n = rec["ingredients"].count(iid)
                price = d["vendor"]["price"] if d.get("vendor") else None
                if price is None:
                    unpriced += n
                else:
                    cost += price * n
                ings.append({"item_id": iid, "name": names.get(iid, ""), "count": n, "status": av.status(iid), "price": price})
            main = rec["results"][0]["item_id"]
            sell = 0
            if main:
                rows = R._rows(conn, "SELECT BaseSell FROM item_basic WHERE itemid=%s", (main,))
                sell = int(rows[0][0] or 0) if rows else 0
            exact, same_result, near = [], [], []
            sig = tuple(sorted(rec["ingredients"]))
            for rc in av._all_recipes():
                if rc["id"] == editing:
                    continue
                brief = {"id": rc["id"], "desynth": rc["desynth"], "result": rc["results"][0]["item_id"],
                         "skills": {k: v for k, v in rc["skills"].items() if v}, "ingredients": rc["ingredients"], "crystal": rc["crystal"]}
                other = tuple(sorted(rc["ingredients"]))
                if rc["desynth"] == rec["desynth"] and rc["crystal"] == rec["crystal"] and other == sig and sig:
                    exact.append(brief)
                elif rc["desynth"] == rec["desynth"] and main and rc["results"][0]["item_id"] == main:
                    same_result.append(brief)
                elif sig and rc["desynth"] == rec["desynth"] and rc["crystal"] == rec["crystal"] and len(other) == len(sig):
                    diff = len(set(sig) ^ set(other))
                    if diff <= 2:
                        near.append(brief)
            nm2 = R.item_names(conn, {b["result"] for b in exact + same_result + near if b["result"]})
            for b in exact + same_result + near:
                b["name"] = nm2.get(b["result"], "")
            return JSONResponse({"errors": errors, "warnings": warnings, "ingredients": ings, "cost": cost, "unpriced": unpriced,
                                 "npc_value": sell * max(1, rec["results"][0]["qty"] or 1), "exact": exact[:10],
                                 "same_result": same_result[:10], "near": near[:10]})
    return _guard(go)


@router.get("/synth/research.json")
def research_json(other: int = Query(0, ge=0)):
    def go():
        with _ctx() as (ctx, root):
            if not other:
                return JSONResponse(A.research(ctx.service.connection, root))
            prof = _other_root(other)
            ctx_b = open_auction_house(prof.root_path)
            try:
                return JSONResponse(A.research(ctx.service.connection, root, (prof.name, ctx_b.service.connection)))
            finally:
                ctx_b.close()
    return _guard(go)


@router.get("/synth/gaps.json")
def gaps_json(limit: int = Query(300, ge=1, le=1000)):
    """Missing ingredients matched to thin guild shops, cross-checked against every other configured environment."""
    def go():
        from workbench.runtime.legacy_settings import get_server_profiles
        with _ctx() as (ctx, root):
            others, opened = [], []
            try:
                for p in get_server_profiles(include_disabled=False):
                    if getattr(p, "active", False) or str(p.root_path) == str(root):
                        continue
                    try:
                        c = open_auction_house(p.root_path)
                    except Exception:
                        continue
                    opened.append(c); others.append((p.name, c.service.connection))
                return JSONResponse(A.vendor_candidates(ctx.service.connection, root, others, limit))
            finally:
                for c in opened:
                    c.close()
    return _guard(go)
