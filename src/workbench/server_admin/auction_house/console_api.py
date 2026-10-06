"""Unified Auction House admin console: aggregate read views, lookups and guarded restock."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import statistics
import sys
import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
from workbench.runtime.paths import GUI_ROOT

from .activity import record_executor_result
from .analytics import search_items
from .factory import open_auction_house
from .legacy_test_executor import (
    LegacyTestExecutionBlocked,
    evaluate_legacy_test_write_gate,
    execute_legacy_test_synthetic_listing,
)
from .listing_management import ListingFilter, browse_active_listings
from .reward_delivery import _char_columns

from .presets import PresetError, get_default_seller, get_preset, seed_builtin_presets, set_default_seller
from .restock_presets import resolve_items

router = APIRouter(tags=["Auction House Console"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))

_MAX_RESTOCK_ENTRIES = 50
_MAX_RESTOCK_ROWS = 500
_MAX_LISTINGS_SCAN = 50000


def _sync_host_template_globals() -> None:
    for module_name in ("gui_server", "__main__"):
        host = sys.modules.get(module_name)
        host_templates = getattr(host, "templates", None) if host is not None else None
        host_env = getattr(host_templates, "env", None)
        host_globals = getattr(host_env, "globals", None)
        if host_globals:
            templates.env.globals.update(host_globals)
            return


@contextmanager
def _context():
    root = get_active_server_root()
    if root is None:
        raise RuntimeError("No active DSP/Topaz server environment is configured")
    ctx = open_auction_house(root)
    try:
        yield ctx
    finally:
        ctx.close()


def _aggregate(rows: list[dict[str, Any]], now: int) -> dict[str, Any]:
    items: dict[int, dict[str, Any]] = {}
    sellers: dict[int, dict[str, Any]] = {}
    for r in rows:
        age = (now - r["listed_at"]) / 86400.0 if r["listed_at"] else None
        it = items.setdefault(r["item_id"], {
            "item_id": r["item_id"], "item_name": r["item_name"], "category_path": r["category_path"],
            "stack_size": r["stack_size"], "listings": 0, "units": 0, "value": 0, "prices": [],
            "sellers": set(), "oldest_days": None,
        })
        it["listings"] += 1
        it["units"] += r["quantity"]
        it["value"] += r["asking_price"]
        it["prices"].append(r["asking_price"])
        it["sellers"].add(r["seller_id"])
        if age is not None and (it["oldest_days"] is None or age > it["oldest_days"]):
            it["oldest_days"] = age
        se = sellers.setdefault(r["seller_id"], {
            "seller_id": r["seller_id"], "seller_name": r["seller_name"], "listings": 0, "value": 0,
            "items": set(), "oldest_days": None,
        })
        se["listings"] += 1
        se["value"] += r["asking_price"]
        se["items"].add(r["item_id"])
        if age is not None and (se["oldest_days"] is None or age > se["oldest_days"]):
            se["oldest_days"] = age
    item_rows = []
    for it in items.values():
        prices = it.pop("prices")
        it["min_price"] = min(prices)
        it["max_price"] = max(prices)
        it["median_price"] = statistics.median(prices)
        it["seller_count"] = len(it.pop("sellers"))
        item_rows.append(it)
    seller_rows = []
    for se in sellers.values():
        se["item_count"] = len(se.pop("items"))
        seller_rows.append(se)
    item_rows.sort(key=lambda x: x["item_name"].lower())
    seller_rows.sort(key=lambda x: (-x["listings"], x["seller_id"]))
    return {"items": item_rows, "sellers": seller_rows}


@router.get("/auction-house/console")
def console_page_alias(request: Request):
    return RedirectResponse("/auction-house" + ("#" + request.url.fragment if request.url.fragment else ""), status_code=307)


@router.get("/auction-house/console/aggregate.json")
def console_aggregate():
    """Per-item and per-seller roll-ups of every active listing (single pass)."""
    try:
        with _context() as ctx:
            now = int(time.time())
            rows = browse_active_listings(ctx.service, ListingFilter(limit=_MAX_LISTINGS_SCAN))
            agg = _aggregate(rows, now)
            ages = [(now - r["listed_at"]) / 86400.0 for r in rows if r["listed_at"]]
            return JSONResponse({
                "generated_at": now, "listing_count": len(rows),
                "truncated": len(rows) >= _MAX_LISTINGS_SCAN,
                "total_value": sum(r["asking_price"] for r in rows),
                "oldest_days": max(ages) if ages else None,
                "stale_30d": sum(1 for a in ages if a >= 30),
                **agg,
            })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/console/listings.json")
def console_listings(
    seller_id: int | None = Query(default=None, ge=1),
    item_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=1000, ge=1, le=5000),
):
    """All active listings for one seller or one item, with ages and a stable ordering."""
    if seller_id is None and item_id is None:
        raise HTTPException(status_code=400, detail="seller_id or item_id is required")
    try:
        with _context() as ctx:
            rows = browse_active_listings(ctx.service, ListingFilter(seller_id=seller_id, item_id=item_id, limit=limit))
            rows.sort(key=lambda r: (r["asking_price"], r["auction_id"]))
            return JSONResponse({"count": len(rows), "rows": rows, "generated_at": int(time.time())})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/console/seller-stats.json")
def console_seller_stats(seller_id: int = Query(ge=1), days: int = Query(default=30, ge=1, le=365)):
    from .economy_intelligence import _load_records, _now_epoch, seller_stats_from
    try:
        with _context() as ctx:
            records, _ = _load_records(ctx.service, days=days)
            return JSONResponse(seller_stats_from(records, seller_id, _now_epoch(), days))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/console/item-search.json")
def console_item_search(q: str = "", category_id: int | None = Query(default=None, ge=1), limit: int = Query(default=25, ge=1, le=250)):
    try:
        with _context() as ctx:
            rows = search_items(ctx.service, q, category_id=category_id, limit=limit)
            return JSONResponse({"rows": rows})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/console/characters.json")
def console_characters(q: str = "", limit: int = Query(default=25, ge=1, le=100), include_sellers: bool = False):
    """Player lookup by character name/id or account login. include_sellers also returns AH-only sellers
    (e.g. synthetic ones) that have no chars row, for use in listing filters."""
    try:
        with _context() as ctx:
            conn = ctx.service.connection
            id_col, name_col = _char_columns(conn)
            term = q.strip()
            like = f"%{term}%"
            num = int(term) if term.isdigit() else -1
            cur = conn.cursor()
            try:
                cur.execute("DESCRIBE `chars`")
                has_acc = "accid" in {str(r[0]) for r in cur.fetchall() or []}
                acc = "c.`accid`" if has_acc else "0"
                join = "LEFT JOIN `accounts` a ON a.`id`=c.`accid`" if has_acc else ""
                login = "a.`login`" if has_acc else "NULL"
                where = f"c.`{name_col}` LIKE %s OR c.`{id_col}`=%s" + (" OR a.`login` LIKE %s OR c.`accid`=%s" if has_acc else "")
                args = (like, num) + ((like, num) if has_acc else ()) + (limit,)
                cur.execute(f"SELECT c.`{id_col}`,c.`{name_col}`,{acc},{login} FROM `chars` c {join} "
                            f"WHERE {where} ORDER BY c.`{name_col}` LIMIT %s", args)
                rows = [{"char_id": int(r[0]), "char_name": str(r[1] or ""), "accid": int(r[2] or 0) or None,
                         "login": r[3], "source": "character"} for r in cur.fetchall() or []]
                if include_sellers and term and len(rows) < limit:
                    seen = {r["char_id"] for r in rows}
                    a_cols = ctx.service.schema.auction_columns
                    if a_cols.get("seller_name") and a_cols.get("seller_id"):
                        sid, sname = ctx.service.q(a_cols["seller_id"]), ctx.service.q(a_cols["seller_name"])
                        cur.execute(f"SELECT DISTINCT {sid},{sname} FROM `auction_house` WHERE {sname} LIKE %s OR {sid}=%s LIMIT %s",
                                    (like, num, limit))
                        for r in cur.fetchall() or []:
                            if int(r[0]) not in seen:
                                rows.append({"char_id": int(r[0]), "char_name": str(r[1] or ""), "accid": None,
                                             "login": None, "source": "auction-only"})
            finally:
                cur.close()
            return JSONResponse({"rows": rows[:limit]})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


_MAX_RESTOCK_SELLERS = 25


def _restock_plan(service, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise LegacyTestExecutionBlocked("Restock requires at least one entry")
    if len(entries) > _MAX_RESTOCK_ENTRIES:
        raise LegacyTestExecutionBlocked(f"Restock is limited to {_MAX_RESTOCK_ENTRIES} items")
    plan: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in entries:
        item_id = int(raw.get("item_id") or 0)
        target = int(raw.get("target") or 0)
        price = int(raw.get("price") or 0)
        if item_id <= 0 or target <= 0 or price <= 0:
            raise LegacyTestExecutionBlocked("Every restock entry needs positive item_id, target and price")
        if item_id in seen:
            raise LegacyTestExecutionBlocked(f"Duplicate item in restock: {item_id}")
        seen.add(item_id)
        snap = service.item_snapshot(item_id)
        if not snap or snap["category_id"] <= 0:
            raise LegacyTestExecutionBlocked(f"Item {item_id} is not an Auction House item")
        stack = bool(raw.get("stack"))
        if stack and snap["stack_size"] <= 1:
            raise LegacyTestExecutionBlocked(f"Item {item_id} cannot be listed as a stack")
        current = len(service.active_listings(item_id, limit=1000))
        plan.append({
            "item_id": item_id, "item_name": snap["name"], "stack": stack, "stack_size": snap["stack_size"],
            "price": price, "target": target, "current": current, "needed": max(0, target - current),
        })
    if sum(p["needed"] for p in plan) > _MAX_RESTOCK_ROWS:
        raise LegacyTestExecutionBlocked(f"Restock would create more than {_MAX_RESTOCK_ROWS} listings")
    return plan


def _restock_token(seller_ids, plan: list[dict[str, Any]]) -> str:
    material = {"seller_ids": list(seller_ids) if isinstance(seller_ids, (list, tuple)) else [seller_ids], "plan": plan}
    return sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _restock_seller(service, seller_id: int) -> dict[str, Any]:
    if int(seller_id) <= 0:
        raise LegacyTestExecutionBlocked("seller_id must be positive")
    seller = service.character_snapshot(int(seller_id))
    if seller:
        return seller
    default = get_default_seller()
    if int(seller_id) == default["char_id"]:
        return dict(default, virtual=True)
    raise LegacyTestExecutionBlocked("Restock seller character does not exist")


def _restock_sellers(service, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One or more seller characters (seller_ids, or legacy seller_id); none means the default synthetic seller.
    Duplicates dropped, order kept."""
    raw = payload.get("seller_ids")
    if isinstance(raw, list) and raw:
        ids = [int(x) for x in raw]
    elif int(payload.get("seller_id") or 0) > 0:
        ids = [int(payload["seller_id"])]
    else:
        ids = [get_default_seller()["char_id"]]
    if len(ids) > _MAX_RESTOCK_SELLERS:
        raise LegacyTestExecutionBlocked(f"Restock is limited to {_MAX_RESTOCK_SELLERS} seller characters")
    out, seen = [], set()
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(_restock_seller(service, i))
    return out


def _assign_sellers(plan: list[dict[str, Any]], sellers: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int]]:
    """Spread each item's new listings across the sellers round-robin, rotating the start per item so no one
    character gets every first listing. Deterministic, so preview and execute agree."""
    out, n = [], len(sellers)
    for k, p in enumerate(plan):
        for j in range(p["needed"]):
            out.append((p, sellers[(k + j) % n]["char_id"]))
    return out


@router.get("/auction-house/console/restock/default-seller.json")
def restock_default_seller():
    return JSONResponse(get_default_seller())


@router.post("/auction-house/console/restock/default-seller.json")
def restock_set_default_seller(payload: dict = Body(...)):
    try:
        return JSONResponse(set_default_seller(int(payload.get("char_id") or 0), str(payload.get("char_name") or "")))
    except PresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/auction-house/console/restock/from-preset.json")
def restock_from_preset(payload: dict = Body(...)):
    """Resolve a saved restock preset to table rows against live data (read-only)."""
    try:
        seed_builtin_presets()
        preset = get_preset(str(payload.get("preset_id") or ""))
        if preset["kind"] != "restock":
            raise PresetError("That preset is not a restock preset")
        with _context() as ctx:
            res = resolve_items(ctx.service, preset["config"])
            sellers = [s for s in (ctx.service.character_snapshot(i) for i in preset["config"].get("seller_ids", [])) if s]
        return JSONResponse(dict(res, preset={"preset_id": preset["preset_id"], "name": preset["name"]}, sellers=sellers, default_seller=get_default_seller()))
    except PresetError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/auction-house/console/restock/preset-test.json")
def restock_preset_test(payload: dict = Body(...)):
    """Resolve an unsaved preset config (editor 'Test') without storing it."""
    try:
        with _context() as ctx:
            return JSONResponse(resolve_items(ctx.service, dict(payload.get("config") or {})))
    except PresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/auction-house/console/restock/preview.json")
def restock_preview(payload: dict = Body(...)):
    try:
        with _context() as ctx:
            sellers = _restock_sellers(ctx.service, payload)
            plan = _restock_plan(ctx.service, list(payload.get("entries") or []))
        counts: dict[int, int] = {}
        for _p, sid in _assign_sellers(plan, sellers):
            counts[sid] = counts.get(sid, 0) + 1
        return JSONResponse({
            "status": "preview", "operation": "restock", "seller": sellers[0], "sellers": [dict(x, listings=counts.get(x["char_id"], 0)) for x in sellers], "plan": plan,
            "listing_rows": sum(p["needed"] for p in plan),
            "preview_token": _restock_token([x["char_id"] for x in sellers], plan),
            "note": "Synthetic supply: no player inventory is removed and no listing fee is charged.",
        })
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/auction-house/test-write/restock.json")
def restock_execute(payload: dict = Body(...)):
    try:
        confirmation = str(payload.get("confirmation") or "")
        environment = get_active_server_identity()
        with _context() as ctx:
            service = ctx.service
            gate = evaluate_legacy_test_write_gate(
                environment=environment, schema_family_hint=service.schema.family_hint,
                confirmation=confirmation, feature_enabled=None,
            )
            if not gate.ready:
                codes = ", ".join(i.code for i in gate.issues if i.blocking)
                raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")
            sellers = _restock_sellers(service, payload)
            plan = _restock_plan(service, list(payload.get("entries") or []))
            if str(payload.get("preview_token") or "") != _restock_token([x["char_id"] for x in sellers], plan):
                raise LegacyTestExecutionBlocked("Restock preview is stale; preview again")
            results, committed, failed = [], 0, 0
            virtual = {x["char_id"]: x["char_name"] for x in sellers if x.get("virtual")}
            for p, sid in _assign_sellers(plan, sellers):
                try:
                    r = execute_legacy_test_synthetic_listing(
                        service=service, environment=environment, item_id=p["item_id"],
                        seller_id=sid, price=p["price"], stack=p["stack"],
                        confirmation=confirmation, virtual_seller_name=virtual.get(sid),
                    )
                    committed += 1
                    results.append({"item_id": p["item_id"], "status": "committed", "auction_id": r.get("auction_id"), "seller_id": sid})
                except Exception as exc:
                    failed += 1
                    results.append({"item_id": p["item_id"], "status": "failed", "error": str(exc), "seller_id": sid})
            result = {
                "status": "completed" if failed == 0 else ("failed" if committed == 0 else "partial"),
                "operation": "restock", "test_only": True, "synthetic": True,
                "seller_id": sellers[0]["char_id"], "seller_ids": [x["char_id"] for x in sellers], "attempted": committed + failed,
                "committed": committed, "failed": failed, "results": results,
            }
        try:
            record_executor_result(environment=environment, result=result, request_payload=payload, operation="restock")
        except Exception:
            pass
        return JSONResponse(result)
    except LegacyTestExecutionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
