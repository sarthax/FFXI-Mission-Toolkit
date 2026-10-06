"""Pure buyer-side analytics over AH records (no DB access, safe to unit test)."""
from __future__ import annotations

import statistics
from typing import Any

_MIN_REF_SALES = 3
OVERPAID_PCT = 50.0   # a purchase this far above the item's median counts as "overpaid"


def _key(r: dict[str, Any]) -> str:
    """DSP stores only buyer_name on sold rows; key by lowercase name, falling back to id."""
    return str(r.get("buyer_name") or "").strip().lower() or (f"#{r['buyer_id']}" if r.get("buyer_id") else "")


def _refs(records: list[dict[str, Any]], cut: int) -> dict[tuple[int, bool], float]:
    """Median sale price per (item, stack?) over the window; only keys with enough sales."""
    groups: dict[tuple[int, bool], list[int]] = {}
    for r in records:
        if r["sold_at"] and r["sold_at"] >= cut and r["sale_price"] > 0:
            groups.setdefault((r["item_id"], bool(r["stack"])), []).append(int(r["sale_price"]))
    return {k: statistics.median(v) for k, v in groups.items() if len(v) >= _MIN_REF_SALES}


def _purchase(r: dict[str, Any], refs: dict) -> dict[str, Any]:
    ref = refs.get((r["item_id"], bool(r["stack"])))
    price = int(r["sale_price"])
    return {
        "auction_id": r["auction_id"], "item_id": r["item_id"], "item_name": r["item_name"], "stack": bool(r["stack"]),
        "price": price, "asking_price": int(r["asking_price"]), "sold_at": r["sold_at"], "listed_at": r["listed_at"],
        "seller_id": r["seller_id"], "seller_name": r["seller_name"],
        "median": None if ref is None else round(ref),
        "markup_pct": None if not ref else round((price / ref - 1) * 100, 1),
        "overpaid_by": None if not ref else max(0, price - round(ref)),
    }


def buyers_from(records: list[dict[str, Any]], now: int, days: int = 30) -> dict[str, Any]:
    cut = now - days * 86400
    refs = _refs(records, cut)
    buyers: dict[int, dict[str, Any]] = {}
    for r in records:
        if not r["sold_at"] or r["sold_at"] < cut or not _key(r):
            continue
        p = _purchase(r, refs)
        b = buyers.setdefault(_key(r), {"buyer_key": _key(r), "buyer_id": r.get("buyer_id"), "buyer_name": r.get("buyer_name") or "",
                                                   "purchases": 0, "spent": 0, "items": set(), "sellers": set(), "last_at": 0,
                                                   "overpaid_count": 0, "overpaid_gil": 0, "markups": [], "biggest": 0})
        b["purchases"] += 1
        b["spent"] += p["price"]
        b["items"].add(p["item_id"])
        b["sellers"].add(p["seller_id"])
        b["last_at"] = max(b["last_at"], p["sold_at"])
        b["biggest"] = max(b["biggest"], p["price"])
        if p["markup_pct"] is not None:
            b["markups"].append(p["markup_pct"])
            if p["markup_pct"] >= OVERPAID_PCT:
                b["overpaid_count"] += 1
                b["overpaid_gil"] += p["overpaid_by"]
    rows = []
    for b in buyers.values():
        mk = b.pop("markups")
        b["distinct_items"] = len(b.pop("items"))
        b["distinct_sellers"] = len(b.pop("sellers"))
        b["avg_markup_pct"] = round(statistics.mean(mk), 1) if mk else None
        rows.append(b)
    rows.sort(key=lambda b: -b["spent"])
    return {"days": days, "count": len(rows), "total_spent": sum(b["spent"] for b in rows),
            "total_purchases": sum(b["purchases"] for b in rows), "overpaid_threshold_pct": OVERPAID_PCT, "buyers": rows}


def buyer_detail_from(records: list[dict[str, Any]], buyer: str, now: int, days: int = 30) -> dict[str, Any]:
    cut = now - days * 86400
    refs = _refs(records, cut)
    mine = sorted((r for r in records if _key(r) == buyer.strip().lower() and r["sold_at"] and r["sold_at"] >= cut), key=lambda r: -r["sold_at"])
    purchases = [_purchase(r, refs) for r in mine]
    items: dict[int, dict[str, Any]] = {}
    sellers: dict[int, dict[str, Any]] = {}
    for p in purchases:
        i = items.setdefault(p["item_id"], {"item_id": p["item_id"], "item_name": p["item_name"], "count": 0, "spent": 0})
        i["count"] += 1; i["spent"] += p["price"]
        s = sellers.setdefault(p["seller_id"], {"seller_id": p["seller_id"], "seller_name": p["seller_name"], "count": 0, "spent": 0})
        s["count"] += 1; s["spent"] += p["price"]
    over = [p for p in purchases if p["markup_pct"] is not None and p["markup_pct"] >= OVERPAID_PCT]
    return {"buyer_key": buyer.strip().lower(), "buyer_name": (mine[0].get("buyer_name") if mine else "") or "", "days": days,
            "purchases": len(purchases), "spent": sum(p["price"] for p in purchases),
            "overpaid_count": len(over), "overpaid_gil": sum(p["overpaid_by"] for p in over),
            "overpaid_threshold_pct": OVERPAID_PCT,
            "top_items": sorted(items.values(), key=lambda x: -x["spent"])[:10],
            "top_sellers": sorted(sellers.values(), key=lambda x: -x["spent"])[:10],
            "rows": purchases[:500]}
