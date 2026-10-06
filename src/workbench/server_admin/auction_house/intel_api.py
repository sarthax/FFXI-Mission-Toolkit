"""Read-only AH history intelligence: seller / buyer ledgers and cross-account player profiles."""
from __future__ import annotations

from .schema import sellable_clause

_AI, _AIB = "i", "ib"

from collections import defaultdict
from contextlib import contextmanager
import statistics
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .categories import category_metadata
from .factory import open_auction_house

router = APIRouter(tags=["Auction House Intelligence"])
_MAX_ROWS = 200000


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


def _rows(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return list(cur.fetchall() or [])
    finally:
        cur.close()


def _table_columns(conn, table: str) -> set[str]:
    try:
        return {str(r[0]) for r in _rows(conn, f"DESCRIBE `{table}`")}
    except Exception:
        return set()


def _load(service, days: int) -> list[dict[str, Any]]:
    """Every auction row that is active or sold inside the window, with item name and category."""
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    for need in ("id", "item_id", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at"):
        if not a.get(need):
            raise RuntimeError("Auction House schema is missing history columns")
    sn = f"ah.{qn(a['seller_name'])}" if a.get("seller_name") else "NULL"
    bn = f"ah.{qn(a['buyer_name'])}" if a.get("buyer_name") else "NULL"
    stack = f"ah.{qn(a['stack'])}" if a.get("stack") else "0"
    cutoff = 0 if days <= 0 else int(time.time()) - days * 86400
    sql = (f"SELECT ah.{qn(a['id'])},ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},{stack},"
           f"ah.{qn(a['seller_id'])},{sn},{bn},ah.{qn(a['listed_at'])},ah.{qn(a['asking_price'])},"
           f"ah.{qn(a['sale_price'])},ah.{qn(a['sold_at'])} FROM `auction_house` ah JOIN `item_basic` i "
           f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
           f"WHERE ah.{qn(a['sold_at'])}=0 OR ah.{qn(a['sold_at'])}>=%s ORDER BY ah.{qn(a['id'])} DESC LIMIT %s")
    out = []
    for r in _rows(service.connection, sql, (cutoff, _MAX_ROWS)):
        out.append({"auction_id": int(r[0]), "item_id": int(r[1]), "item_name": str(r[2] or ""),
                    "category_id": int(r[3] or 0), "stack": bool(r[4]), "seller_id": int(r[5] or 0),
                    "seller_name": r[6] or "", "buyer_name": r[7] or "", "listed_at": int(r[8] or 0),
                    "asking": int(r[9] or 0), "price": int(r[10] or 0), "sold_at": int(r[11] or 0)})
    return out


def _day(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _chars(conn) -> dict[str, dict[str, Any]]:
    """charname(lower) -> {char_id, accid}."""
    cols = _table_columns(conn, "chars")
    if not {"charid", "charname"} <= cols:
        return {}
    acc = "accid" if "accid" in cols else "0"
    return {str(n).lower(): {"char_id": int(c), "accid": int(a)} for c, n, a in
            _rows(conn, f"SELECT charid,charname,{acc} FROM chars")}


def _summary(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    sold = [r for r in rows if r["sold_at"]]
    active = [r for r in rows if not r["sold_at"]]
    prices = [r["price"] for r in sold if r["price"] > 0]
    other = "buyer_name" if role == "seller" else "seller_name"
    return {"sold_count": len(sold), "sold_gil": sum(prices),
            "avg_price": int(sum(prices) / len(prices)) if prices else None,
            "median_price": int(statistics.median(prices)) if prices else None,
            "active_count": len(active), "active_value": sum(r["asking"] for r in active),
            "distinct_items": len({r["item_id"] for r in rows}),
            "counterparties": len({str(r[other]).lower() for r in sold if r[other]}),
            "first": min((r["sold_at"] for r in sold), default=None),
            "last": max((r["sold_at"] for r in sold), default=None)}


def _detail(rows: list[dict[str, Any]], role: str) -> dict[str, Any]:
    sold = [r for r in rows if r["sold_at"]]
    days: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    items: dict[int, dict[str, Any]] = {}
    other = "buyer_name" if role == "seller" else "seller_name"
    cp: dict[str, dict[str, Any]] = {}
    both: dict[str, dict[str, dict[str, Any]]] = {"seller_name": {}, "buyer_name": {}}
    for r in sold:
        for fld, bucket in both.items():
            nm = str(r[fld] or "(unknown)")
            b = bucket.setdefault(nm.lower(), {"name": nm, "count": 0, "gil": 0})
            b["count"] += 1
            b["gil"] += r["price"]
        d = days[_day(r["sold_at"])]
        d[0] += 1
        d[1] += r["price"]
        e = items.setdefault(r["item_id"], {"item_id": r["item_id"], "item_name": r["item_name"], "count": 0, "gil": 0})
        e["count"] += 1
        e["gil"] += r["price"]
        name = str(r[other] or "(unknown)")
        c = cp.setdefault(name.lower(), {"name": name, "count": 0, "gil": 0})
        c["count"] += 1
        c["gil"] += r["price"]
    recent = sorted(sold, key=lambda r: r["sold_at"], reverse=True)[:60]
    return {"summary": _summary(rows, role),
            "series": [{"day": k, "count": v[0], "gil": v[1]} for k, v in sorted(days.items())],
            "top_items": sorted(items.values(), key=lambda e: e["gil"], reverse=True)[:15],
            "counterparties": sorted(cp.values(), key=lambda e: e["gil"], reverse=True)[:15],
            "top_sellers": sorted(both["seller_name"].values(), key=lambda e: e["gil"], reverse=True)[:15],
            "top_buyers": sorted(both["buyer_name"].values(), key=lambda e: e["gil"], reverse=True)[:15],
            "recent": [{"auction_id": r["auction_id"], "item_id": r["item_id"], "item_name": r["item_name"],
                        "stack": r["stack"], "seller": r["seller_name"], "buyer": r["buyer_name"],
                        "asking": r["asking"], "price": r["price"], "listed_at": r["listed_at"],
                        "sold_at": r["sold_at"]} for r in recent]}


@router.get("/auction-house/intel/ledger.json")
def ledger(role: str = Query(pattern="^(seller|buyer)$"), days: int = Query(default=30, ge=0, le=3650),
           q: str = "", limit: int = Query(default=300, ge=1, le=1000)):
    """days=0 means all time. Buyer rows are keyed by name: auction_house stores no buyer id."""
    try:
        with _context() as ctx:
            rows = _load(ctx.service, days)
            chars = _chars(ctx.service.connection)
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in rows:
                if role == "seller":
                    groups[str(r["seller_id"])].append(r)
                elif r["sold_at"] and r["buyer_name"]:
                    groups[r["buyer_name"].lower()].append(r)
            term = q.strip().lower()
            out = []
            for key, g in groups.items():
                name = g[0]["seller_name"] if role == "seller" else g[0]["buyer_name"]
                ch = chars.get(str(name).lower(), {})
                cid = int(key) if role == "seller" else ch.get("char_id")
                if term and term not in str(name).lower() and term != str(cid):
                    continue
                out.append({"key": key, "name": name or f"#{key}", "char_id": cid, "accid": ch.get("accid"),
                            **_summary(g, role)})
            out.sort(key=lambda e: (e["sold_gil"], e["active_value"]), reverse=True)
            return JSONResponse({"role": role, "days": days, "rows": out[:limit], "total": len(out),
                                 "note": None if role == "seller" else "Buyers are matched by character name (the AH table stores no buyer id)."})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/intel/detail.json")
def detail(kind: str = Query(pattern="^(seller|buyer|category|item)$"), key: str = Query(min_length=1),
           days: int = Query(default=30, ge=0, le=3650)):
    try:
        with _context() as ctx:
            rows = _load(ctx.service, days)
            k = key.strip().lower()
            if kind == "seller":
                sel = [r for r in rows if str(r["seller_id"]) == k]
            elif kind == "buyer":
                sel = [r for r in rows if r["sold_at"] and r["buyer_name"].lower() == k]
            elif kind == "category":
                sel = [r for r in rows if str(r["category_id"]) == k]
            else:
                sel = [r for r in rows if str(r["item_id"]) == k]
            label = key
            if sel:
                label = {"seller": sel[0]["seller_name"], "buyer": sel[0]["buyer_name"], "item": sel[0]["item_name"],
                         "category": category_metadata(sel[0]["category_id"]).path}[kind] or key
            return JSONResponse({"kind": kind, "key": key, "label": label, "days": days,
                                 **_detail(sel, "buyer" if kind == "buyer" else "seller")})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _accounts(conn, accids: list[int]) -> list[dict[str, Any]]:
    if not accids:
        return []
    ph = ",".join(["%s"] * len(accids))
    logins = {int(i): str(l) for i, l in _rows(conn, f"SELECT id,login FROM accounts WHERE id IN ({ph})", tuple(accids))}
    by: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for c, n, a in _rows(conn, f"SELECT charid,charname,accid FROM chars WHERE accid IN ({ph}) ORDER BY charid", tuple(accids)):
        by[int(a)].append({"char_id": int(c), "name": str(n)})
    return [{"accid": a, "login": logins.get(a, ""), "characters": by.get(a, [])} for a in accids]


@router.get("/auction-house/intel/people.json")
def people(q: str = Query(min_length=1), limit: int = Query(default=30, ge=1, le=100)):
    """Search by character name/id, account login/id or IP; one row per account with all its characters."""
    try:
        with _context() as ctx:
            conn = ctx.service.connection
            term = q.strip()
            like = f"%{term}%"
            digits = int(term) if term.isdigit() else -1
            ids: set[int] = set()
            for (a,) in _rows(conn, "SELECT accid FROM chars WHERE charname LIKE %s OR charid=%s OR accid=%s LIMIT 200", (like, digits, digits)):
                ids.add(int(a))
            for (a,) in _rows(conn, "SELECT id FROM accounts WHERE login LIKE %s OR id=%s LIMIT 200", (like, digits)):
                ids.add(int(a))
            if _table_columns(conn, "account_ip_record"):
                for (a,) in _rows(conn, "SELECT DISTINCT accid FROM account_ip_record WHERE client_ip LIKE %s LIMIT 200", (like,)):
                    ids.add(int(a))
            return JSONResponse({"rows": _accounts(conn, sorted(ids)[:limit])})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/intel/person.json")
def person(accid: int = Query(ge=0), days: int = Query(default=0, ge=0, le=3650)):
    """One account: characters, IP history, accounts sharing those IPs, and combined AH history."""
    try:
        with _context() as ctx:
            conn = ctx.service.connection
            found = _accounts(conn, [accid])
            if not found or (not found[0]["login"] and not found[0]["characters"]):
                raise HTTPException(status_code=404, detail="Account not found")
            main = found[0]
            ip: dict[str, Any] = {"available": False, "records": [], "linked": []}
            if _table_columns(conn, "account_ip_record"):
                ip["available"] = True
                recs = _rows(conn, "SELECT login_time,client_ip FROM account_ip_record WHERE accid=%s ORDER BY login_time DESC LIMIT 2000", (accid,))
                per: dict[str, dict[str, Any]] = {}
                for t, addr in recs:
                    e = per.setdefault(str(addr), {"ip": str(addr), "logins": 0, "first": str(t), "last": str(t)})
                    e["logins"] += 1
                    e["first"] = min(e["first"], str(t))
                    e["last"] = max(e["last"], str(t))
                ip["records"] = sorted(per.values(), key=lambda e: e["last"], reverse=True)
                if per:
                    ph = ",".join(["%s"] * len(per))
                    shared = _rows(conn, f"SELECT DISTINCT accid,client_ip FROM account_ip_record WHERE client_ip IN ({ph}) AND accid<>%s",
                                   (*per, accid))
                    ids = sorted({int(a) for a, _ in shared})
                    names = {a["accid"]: a for a in _accounts(conn, ids)}
                    ip["linked"] = [{**names[a], "shared_ips": sorted({str(i) for x, i in shared if int(x) == a})} for a in ids]

            def ah(accs: list[dict[str, Any]]):
                ids = {c["char_id"] for a in accs for c in a["characters"]}
                names = {c["name"].lower() for a in accs for c in a["characters"]}
                rows = _load(ctx.service, days)
                return {"selling": _detail([r for r in rows if r["seller_id"] in ids], "seller"),
                        "buying": _detail([r for r in rows if r["sold_at"] and r["buyer_name"].lower() in names], "buyer")}

            return JSONResponse({"account": main, "ip": ip, "ah": ah([main]), "days": days,
                                 "ah_with_linked": ah([main, *ip["linked"]]) if ip["linked"] else None})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
