"""Voidwatch domain routes (read-only): NM overview, path graph data, NM dossier."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException, Query

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.server_admin.auction_house.factory import open_auction_house

from . import details as D
from . import drops as Dr
from . import edits as E
from . import npcfix as Nf
from . import officers as Of
from . import backlog as Bk
from . import warps as W

router = APIRouter(tags=["Voidwatch"])


@contextmanager
def _ctx():
    root = get_active_server_root()
    ident = get_active_server_identity()
    if root is None or (ident or {}).get("family") != "dsp":
        raise HTTPException(status_code=503, detail="Voidwatch needs the active server to be the DSP environment (it is " + str((ident or {}).get("name")) + ")")
    ctx = open_auction_house(root)
    try:
        yield ctx, root, ident
    finally:
        ctx.close()


def _guard(fn):
    try:
        return fn()
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown NM {exc}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/domains/voidwatch/overview.json")
def overview_json():
    def go():
        with _ctx() as (ctx, root, ident):
            d = D.overview(ctx.service.connection, root)
            d["server"] = {"name": ident["name"], "environment": ident["environment"], "root": str(root)}
            return d
    return _guard(go)


@router.get("/domains/voidwatch/nm.json")
def nm_json(name: str = Query(..., min_length=1)):
    def go():
        with _ctx() as (ctx, root, ident):
            d = D.nm_detail(ctx.service.connection, root, name)
            d["server"] = {"name": ident["name"], "environment": ident["environment"], "root": str(root)}
            return d
    return _guard(go)


@router.post("/domains/voidwatch/validation")
def save_validation(payload: dict = Body(...)):
    def go():
        rec = D.save_validation(str(payload.get("name", "")), payload.get("areas") or {}, str(payload.get("note", "")), str(payload.get("by", "")))
        rec["status"] = D.validation_status(rec)
        return rec
    return _guard(go)


@router.get("/domains/voidwatch/officers.json")
def officers_json():
    def go():
        with _ctx() as (ctx, root, ident):
            return Of.overview(ctx.service.connection, root)
    return _guard(go)


@router.post("/domains/voidwatch/officer-validation")
def officer_validation(payload: dict = Body(...)):
    def go():
        rec = Of.save_validation(str(payload.get("id", "")), payload.get("areas") or {}, str(payload.get("note", "")), str(payload.get("by", "")))
        rec["status"] = Of.validation_status(rec)
        return rec
    return _guard(go)


@router.post("/domains/voidwatch/officer-zone-validation")
def officer_zone_validation(payload: dict = Body(...)):
    def go():
        rec = Of.save_zone_validation(str(payload.get("id", "")), str(payload.get("zone", "")), payload.get("areas") or {}, str(payload.get("note", "")), str(payload.get("by", "")))
        rec["status"] = Of.zone_status(rec)
        return rec
    return _guard(go)


@router.get("/domains/voidwatch/drops.json")
def drops_json():
    def go():
        with _ctx() as (ctx, root, ident):
            cur = Dr.current(root)
            o = cur["overrides"]
            ids = set(cur["placeholder_pool"]) | set(o["pool"]) | set(o["poolRemove"])
            for e in o["nm"].values():
                ids |= set(e["add"]) | set(e["remove"])
            cur["items"] = D._item_names(ctx.service.connection, ids)
            return cur
    return _guard(go)


@router.post("/domains/voidwatch/drops/edit")
def drops_edit(payload: dict = Body(...)):
    """Plan (dry_run, default) or apply one drop-override change to scripts/globals/voidwatch_drops.lua, behind the write gate."""
    from workbench.server_admin.auction_house.legacy_test_executor import evaluate_legacy_test_write_gate

    def go():
        with _ctx() as (ctx, root, ident):
            try:
                p = Dr.plan(ctx.service.connection, root, payload)
            except Dr.DropError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            out = {k: v for k, v in p.items() if k != "new_text"}
            if payload.get("dry_run", True):
                return {"applied": False, **out}
            gate = evaluate_legacy_test_write_gate(environment=ident, schema_family_hint=ctx.service.schema.family_hint,
                                                   confirmation=str(payload.get("confirmation") or ""), feature_enabled=None)
            if not gate.ready:
                raise HTTPException(status_code=409, detail="Write blocked: " + "; ".join(i.message for i in gate.issues if i.blocking))
            Dr.apply(p, str(payload.get("by", "")))
            return {"applied": True, **out}
    return _guard(go)


@router.post("/domains/voidwatch/edit")
def edit(payload: dict = Body(...)):
    """Plan (dry_run, default) or apply one whitelisted row edit on the ACTIVE DSP environment, behind the Test-profile write gate."""
    from workbench.server_admin.auction_house.legacy_test_executor import evaluate_legacy_test_write_gate

    def go():
        with _ctx() as (ctx, root, ident):
            conn = ctx.service.connection
            try:
                p = E.plan(conn, str(payload.get("table", "")), payload.get("key"), payload.get("changes") or {})
            except E.EditError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if payload.get("dry_run", True):
                return {"applied": False, **p}
            gate = evaluate_legacy_test_write_gate(environment=ident, schema_family_hint=ctx.service.schema.family_hint,
                                                   confirmation=str(payload.get("confirmation") or ""), feature_enabled=None)
            if not gate.ready:
                raise HTTPException(status_code=409, detail="Write blocked: " + "; ".join(i.message for i in gate.issues if i.blocking))
            return {"applied": True, "rows": E.apply(conn, p, str(payload.get("by", ""))), **p}
    return _guard(go)


@router.get("/domains/voidwatch/warps.json")
def warps_json():
    def go():
        with _ctx() as (ctx, root, ident):
            return W.overview(ctx.service.connection)
    return _guard(go)


@router.post("/domains/voidwatch/warps/save")
def warps_save(payload: dict = Body(...)):
    def go():
        try:
            return W.save(str(payload.get("id", "")), payload.get("changes") or {}, str(payload.get("by", "")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return _guard(go)


@router.post("/domains/voidwatch/warps/export-lua")
def warps_export(payload: dict = Body(default={})):
    """Write scripts/globals/voidwatch_warps.lua into the DSP script checkout from the validated entries (only complete, ok entries are live)."""
    def go():
        with _ctx() as (ctx, root, ident):
            return W.export_lua(ctx.service.connection, root)
    return _guard(go)


@router.get("/domains/voidwatch/npcfix.json")
def npcfix_json():
    def go():
        with _ctx() as (ctx, root, ident):
            return Nf.overview(ctx.service.connection)
    return _guard(go)


@router.post("/domains/voidwatch/npcfix")
def npcfix(payload: dict = Body(...)):
    """Plan (dry_run, default) or apply one Voidwatch npc_list fix (update / delete / insert) behind the Test-profile write gate."""
    from workbench.server_admin.auction_house.legacy_test_executor import evaluate_legacy_test_write_gate

    def go():
        with _ctx() as (ctx, root, ident):
            conn = ctx.service.connection
            kind = str(payload.get("kind", ""))
            try:
                if kind == "update":
                    p = Nf.plan_update(conn, int(payload.get("npcid")), payload.get("changes") or {})
                elif kind == "delete":
                    p = Nf.plan_delete(conn, int(payload.get("npcid")))
                elif kind == "insert":
                    p = Nf.plan_insert(conn, str(payload.get("npc", "")), str(payload.get("zone", "")),
                                       payload.get("x"), payload.get("y"), payload.get("z"), payload.get("rot"))
                else:
                    raise Nf.FixError("kind must be update, delete or insert")
            except (Nf.FixError, TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            if payload.get("dry_run", True):
                return {"applied": False, **p}
            gate = evaluate_legacy_test_write_gate(environment=ident, schema_family_hint=ctx.service.schema.family_hint,
                                                   confirmation=str(payload.get("confirmation") or ""), feature_enabled=None)
            if not gate.ready:
                raise HTTPException(status_code=409, detail="Write blocked: " + "; ".join(i.message for i in gate.issues if i.blocking))
            return {"applied": True, "rows": Nf.apply(conn, p, str(payload.get("by", ""))), **p}
    return _guard(go)


@router.get("/domains/voidwatch/backlog.json")
def backlog_json():
    return _guard(lambda: Bk.overview())


@router.post("/domains/voidwatch/backlog/save")
def backlog_save(payload: dict = Body(...)):
    def go():
        try:
            return Bk.save(str(payload.get("id", "")), payload.get("changes") or {}, str(payload.get("by", "")))
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return _guard(go)

