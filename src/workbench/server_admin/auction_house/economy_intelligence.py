"""Read-only seller/category Auction House economy intelligence for DSP/Topaz."""
from __future__ import annotations

from .schema import sellable_clause

_AI, _AIB = "i", "ib"

import statistics

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

from .categories import category_metadata
from .legacy_test_executor import LegacyTestExecutionBlocked
from .service import AuctionHouseService

_MAX_SAMPLE_ROWS = 50000
_DEFAULT_SAMPLE_ROWS = 20000


def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _mean(values: list[int]) -> float | None:
    return None if not values else round(sum(values) / len(values), 2)


def _median(values: list[int]) -> float | None:
    return None if not values else round(float(median(values)), 2)


def _aging_bucket(age_days: float) -> str:
    if age_days < 7:
        return "lt_7d"
    if age_days < 30:
        return "7_30d"
    if age_days < 90:
        return "30_90d"
    return "90d_plus"


def _empty_buckets() -> dict[str, int]:
    return {"lt_7d": 0, "7_30d": 0, "30_90d": 0, "90d_plus": 0}


def _load_records(
    service: AuctionHouseService,
    *,
    days: int,
    sample_limit: int = _DEFAULT_SAMPLE_ROWS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load a bounded active+recent-sale sample using discovered schema columns only."""
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    required_a = ("id", "item_id", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at")
    required_i = ("item_id", "name", "ah_category")
    if any(not a.get(name) for name in required_a) or any(not i.get(name) for name in required_i):
        raise LegacyTestExecutionBlocked("Auction House schema is missing economy-intelligence columns")

    safe_days = max(1, min(int(days), 3650))
    safe_limit = max(100, min(int(sample_limit), _MAX_SAMPLE_ROWS))
    now = _now_epoch()
    cutoff = now - safe_days * 86400
    seller_name = f"ah.{qn(a['seller_name'])}" if a.get("seller_name") else "NULL"
    buyer_name = f"ah.{qn(a['buyer_name'])}" if a.get("buyer_name") else "NULL"
    buyer_id = f"ah.{qn(a['buyer_id'])}" if a.get("buyer_id") else "NULL"
    stack_expr = f"ah.{qn(a['stack'])}" if a.get("stack") else "0"

    sql = (
        "SELECT "
        f"ah.{qn(a['id'])},ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},"
        f"{stack_expr},ah.{qn(a['seller_id'])},{seller_name},{buyer_id},{buyer_name},"
        f"ah.{qn(a['listed_at'])},ah.{qn(a['asking_price'])},ah.{qn(a['sale_price'])},ah.{qn(a['sold_at'])} "
        "FROM `auction_house` ah JOIN `item_basic` i "
        f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
        f"WHERE ah.{qn(a['sold_at'])}=0 OR ah.{qn(a['sold_at'])}>=%s "
        f"ORDER BY CASE WHEN ah.{qn(a['sold_at'])}=0 THEN 0 ELSE 1 END,"
        f"ah.{qn(a['listed_at'])} ASC,ah.{qn(a['sold_at'])} DESC LIMIT %s"
    )
    c = service.connection.cursor()
    try:
        c.execute(sql, (cutoff, safe_limit))
        rows = list(c.fetchall() or [])
    finally:
        c.close()

    records = [{
        "auction_id": _safe_int(r[0]),
        "item_id": _safe_int(r[1]),
        "item_name": str(r[2] or ""),
        "category_id": _safe_int(r[3]),
        "stack": bool(r[4]),
        "seller_id": _safe_int(r[5]),
        "seller_name": r[6],
        "buyer_id": None if r[7] is None else _safe_int(r[7]),
        "buyer_name": r[8],
        "listed_at": _safe_int(r[9]),
        "asking_price": _safe_int(r[10]),
        "sale_price": _safe_int(r[11]),
        "sold_at": _safe_int(r[12]),
    } for r in rows]
    return records, {
        "window_days": safe_days,
        "cutoff": cutoff,
        "sample_limit": safe_limit,
        "sample_rows": len(records),
        "sample_truncated": len(records) >= safe_limit,
        "read_only": True,
    }


def _summarize_group(
    rows: list[dict[str, Any]],
    *,
    now: int,
    stale_days: int,
    top_item_limit: int = 10,
) -> dict[str, Any]:
    active = [r for r in rows if not r["sold_at"]]
    sold = [r for r in rows if r["sold_at"]]
    asking = [r["asking_price"] for r in active if r["asking_price"] > 0]
    sale_prices = [r["sale_price"] for r in sold if r["sale_price"] > 0]
    ages = [max(0.0, (now - r["listed_at"]) / 86400.0) for r in active if r["listed_at"] > 0]
    buckets = _empty_buckets()
    for age in ages:
        buckets[_aging_bucket(age)] += 1

    stale = sum(1 for age in ages if age >= stale_days)
    denominator = len(active) + len(sold)
    sell_through = None if denominator == 0 else round((len(sold) / denominator) * 100.0, 2)

    item_stats: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {
        "active_count": 0, "active_value": 0, "sold_count": 0, "sold_value": 0,
    })
    for row in rows:
        key = (row["item_id"], row["item_name"])
        if row["sold_at"]:
            item_stats[key]["sold_count"] += 1
            item_stats[key]["sold_value"] += max(0, row["sale_price"])
        else:
            item_stats[key]["active_count"] += 1
            item_stats[key]["active_value"] += max(0, row["asking_price"])

    top_active = sorted(
        ({"item_id": key[0], "item_name": key[1], **values} for key, values in item_stats.items()),
        key=lambda x: (x["active_value"], x["active_count"]), reverse=True,
    )[:top_item_limit]
    top_sold = sorted(
        ({"item_id": key[0], "item_name": key[1], **values} for key, values in item_stats.items()),
        key=lambda x: (x["sold_value"], x["sold_count"]), reverse=True,
    )[:top_item_limit]

    ttl = [round((r["sold_at"] - r["listed_at"]) / 3600.0, 2) for r in sold if r["listed_at"] > 0 and r["sold_at"] >= r["listed_at"]]
    return {
        "median_hours_to_sale": _median(ttl),
        "active_listings": len(active),
        "active_asking_value": sum(asking),
        "sold_count": len(sold),
        "sold_gil": sum(sale_prices),
        "average_asking_price": _mean(asking),
        "median_asking_price": _median(asking),
        "average_sale_price": _mean(sale_prices),
        "median_sale_price": _median(sale_prices),
        "oldest_active_age_days": None if not ages else round(max(ages), 2),
        "stale_active_count": stale,
        "aging_buckets": buckets,
        "sell_through_pct": sell_through,
        "top_items_by_active_exposure": top_active,
        "top_items_by_realized_volume": top_sold,
    }


def seller_intelligence_from_records(
    records: list[dict[str, Any]], *, now: int, stale_days: int = 30, limit: int = 100,
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[(row["seller_id"], row.get("seller_name"))].append(row)
    rows = []
    for (seller_id, seller_name), group in groups.items():
        summary = _summarize_group(group, now=now, stale_days=stale_days)
        rows.append({"seller_id": seller_id, "seller_name": seller_name, **summary})
    rows.sort(key=lambda r: (r["active_asking_value"] + r["sold_gil"], r["active_listings"]), reverse=True)
    return rows[:max(1, min(int(limit), 500))]


def category_intelligence_from_records(
    records: list[dict[str, Any]], *, now: int, stale_days: int = 30, limit: int = 100,
) -> list[dict[str, Any]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[row["category_id"]].append(row)
    rows = []
    for category_id, group in groups.items():
        summary = _summarize_group(group, now=now, stale_days=stale_days)
        active = [r for r in group if not r["sold_at"]]
        sold = [r for r in group if r["sold_at"]]
        distinct_items = len({r["item_id"] for r in group})
        seller_count = len({r["seller_id"] for r in group if r["seller_id"]})
        recent_sales = len(sold)
        active_count = len(active)
        stale_ratio = 0.0 if active_count == 0 else summary["stale_active_count"] / active_count
        if active_count <= 2 and recent_sales >= 5:
            supply_signal = "undersupplied"
        elif active_count >= 10 and stale_ratio >= 0.5 and recent_sales <= max(1, active_count // 5):
            supply_signal = "stale_or_oversupplied"
        else:
            supply_signal = "balanced_or_insufficient_evidence"
        category = category_metadata(category_id)
        rows.append({
            "category_id": category_id,
            "category_path": category.path,
            "distinct_items": distinct_items,
            "seller_count": seller_count,
            "supply_signal": supply_signal,
            "signal_basis": {
                "active_count": active_count,
                "recent_sales": recent_sales,
                "stale_ratio_pct": round(stale_ratio * 100.0, 2),
                "heuristic": "undersupplied when <=2 active and >=5 recent sales; stale/oversupplied when >=10 active, >=50% stale, and weak recent sales",
            },
            **summary,
        })
    rows.sort(key=lambda r: (r["sold_gil"] + r["active_asking_value"], r["active_listings"]), reverse=True)
    return rows[:max(1, min(int(limit), 500))]


_MIN_MOVER_SALES = 2


def _window_stats(records: list[dict[str, Any]], start: int, end: int) -> dict[str, Any]:
    sold = [r for r in records if start <= r["sold_at"] < end and r["sold_at"]]
    prices = [r["sale_price"] for r in sold if r["sale_price"] > 0]
    ttl = [(r["sold_at"] - r["listed_at"]) / 3600.0 for r in sold if r["listed_at"] > 0 and r["sold_at"] >= r["listed_at"]]
    return {
        "sales": len(sold),
        "gil": sum(prices),
        "median_sale": _median(prices),
        "unique_buyers": len({str(r["buyer_name"]).lower() for r in sold if r.get("buyer_name")}),
        "unique_sellers": len({r["seller_id"] for r in sold if r["seller_id"]}),
        "listed": sum(1 for r in records if r["listed_at"] and start <= r["listed_at"] < end),
        "median_hours_to_sale": _median([round(h, 2) for h in ttl]),
    }


def trends_from_records(records: list[dict[str, Any]], *, now: int, days: int) -> dict[str, Any]:
    """Current window vs the equally long prior window, daily series, and per-item price movers."""
    span = days * 86400
    cur_start, prior_start = now - span, now - 2 * span
    current = _window_stats(records, cur_start, now + 1)
    prior = _window_stats(records, prior_start, cur_start)

    daily: dict[str, dict[str, int]] = {}
    for r in records:
        if r["sold_at"] and r["sold_at"] >= cur_start:
            d = daily.setdefault(datetime.fromtimestamp(r["sold_at"], timezone.utc).strftime("%Y-%m-%d"), {"sales": 0, "gil": 0, "listed": 0})
            d["sales"] += 1
            d["gil"] += max(0, r["sale_price"])
        if r["listed_at"] and r["listed_at"] >= cur_start:
            d = daily.setdefault(datetime.fromtimestamp(r["listed_at"], timezone.utc).strftime("%Y-%m-%d"), {"sales": 0, "gil": 0, "listed": 0})
            d["listed"] += 1
    series = [{"day": k, **v} for k, v in sorted(daily.items())]

    cur_prices: dict[tuple[int, str], list[int]] = defaultdict(list)
    prior_prices: dict[tuple[int, str], list[int]] = defaultdict(list)
    for r in records:
        if not r["sold_at"] or r["sale_price"] <= 0:
            continue
        key = (r["item_id"], r["item_name"])
        if r["sold_at"] >= cur_start:
            cur_prices[key].append(r["sale_price"])
        elif r["sold_at"] >= prior_start:
            prior_prices[key].append(r["sale_price"])
    movers = []
    for key, cp in cur_prices.items():
        pp = prior_prices.get(key)
        if not pp:
            continue
        cm, pm = _median(cp), _median(pp)
        if not pm:
            continue
        movers.append({
            "item_id": key[0], "item_name": key[1], "current_median": cm, "prior_median": pm,
            "change_pct": round((cm - pm) / pm * 100.0, 1), "current_sales": len(cp), "prior_sales": len(pp),
            "reliable": len(cp) >= _MIN_MOVER_SALES and len(pp) >= _MIN_MOVER_SALES,
        })
    movers.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
    return {
        "days": days, "current": current, "prior": prior, "series": series, "movers": movers[:100],
        "min_mover_sales": _MIN_MOVER_SALES,
        "notes": "Prior-period deltas cover sales, gil, buyers, sellers, new listings and time-to-sale. Active-listing and sell-through history is not stored by the server, so those have no prior comparison.",
    }


def economy_trends(service: AuctionHouseService, *, days: int = 7) -> dict[str, Any]:
    days = max(1, min(int(days), 1825))
    records, meta = _load_records(service, days=days * 2, sample_limit=_MAX_SAMPLE_ROWS)
    return {**meta, **trends_from_records(records, now=_now_epoch(), days=days)}


_QUEUE_LIMIT = 15


def queues_from_records(records: list[dict[str, Any]], *, now: int, stale_days: int = 30) -> dict[str, Any]:
    """Operational queues + seller concentration. Transparent thresholds, returned with the result."""
    items: dict[int, dict[str, Any]] = {}
    for r in records:
        it = items.setdefault(r["item_id"], {
            "item_id": r["item_id"], "item_name": r["item_name"], "category_id": r["category_id"],
            "active": 0, "sold": 0, "stale": 0, "ask_total": 0, "oldest_days": 0.0, "sellers": defaultdict(int),
        })
        if r["sold_at"]:
            it["sold"] += 1
        else:
            it["active"] += 1
            it["ask_total"] += max(0, r["asking_price"])
            it["sellers"][r["seller_name"] or f"#{r['seller_id']}"] += 1
            if r["listed_at"]:
                age = max(0.0, (now - r["listed_at"]) / 86400.0)
                it["oldest_days"] = max(it["oldest_days"], age)
                if age >= stale_days:
                    it["stale"] += 1

    def row(it: dict[str, Any], **extra: Any) -> dict[str, Any]:
        total = it["active"] + it["sold"]
        return {"item_id": it["item_id"], "item_name": it["item_name"],
                "category_path": category_metadata(it["category_id"]).path,
                "active": it["active"], "sold": it["sold"],
                "sell_through_pct": None if not total else round(it["sold"] / total * 100.0, 1), **extra}

    needs, over, stagnant, conc = [], [], [], []
    for it in items.values():
        total = it["active"] + it["sold"]
        if it["active"] <= 1 and it["sold"] >= 3:
            needs.append(row(it, score=it["sold"] - it["active"]))
        if it["active"] >= 5 and total and it["sold"] / total < 0.2:
            over.append(row(it, score=it["active"] - it["sold"], ask_total=it["ask_total"]))
        if it["stale"] > 0 and it["sold"] == 0:
            stagnant.append(row(it, score=it["stale"], stale=it["stale"], oldest_days=round(it["oldest_days"], 1)))
        if it["active"] >= 3:
            name, n = max(it["sellers"].items(), key=lambda kv: kv[1])
            share = n / it["active"] * 100.0
            if share >= 70.0:
                conc.append(row(it, score=share, top_seller=name, share_pct=round(share, 1)))
    for lst in (needs, over, stagnant, conc):
        lst.sort(key=lambda x: x["score"], reverse=True)
    return {
        "needs_supply": needs[:_QUEUE_LIMIT], "oversupplied": over[:_QUEUE_LIMIT],
        "stagnant": stagnant[:_QUEUE_LIMIT], "concentration": conc[:_QUEUE_LIMIT],
        "counts": {"needs_supply": len(needs), "oversupplied": len(over), "stagnant": len(stagnant), "concentration": len(conc)},
        "rules": {
            "needs_supply": "<=1 active listing and >=3 sales in the window",
            "oversupplied": ">=5 active listings and <20% sell-through",
            "stagnant": f"has listings older than {stale_days} days and no sales in the window",
            "concentration": ">=3 active listings and one seller holds >=70% of them (an investigation signal, not a finding)",
        },
    }


def economy_intelligence(
    service: AuctionHouseService,
    *,
    days: int = 30,
    stale_days: int = 30,
    seller_id: int | None = None,
    category_id: int | None = None,
    limit: int = 100,
    sample_limit: int = _DEFAULT_SAMPLE_ROWS,
) -> dict[str, Any]:
    records, meta = _load_records(service, days=days, sample_limit=sample_limit)
    now = _now_epoch()
    stale_days = max(1, min(int(stale_days), 3650))
    if seller_id is not None:
        records = [r for r in records if r["seller_id"] == int(seller_id)]
    if category_id is not None:
        records = [r for r in records if r["category_id"] == int(category_id)]
    sellers = seller_intelligence_from_records(records, now=now, stale_days=stale_days, limit=limit)
    categories = category_intelligence_from_records(records, now=now, stale_days=stale_days, limit=limit)
    return {
        **meta,
        "stale_threshold_days": stale_days,
        "filters": {"seller_id": seller_id, "category_id": category_id},
        "seller_rows": sellers,
        "category_rows": categories,
        "totals": _summarize_group(records, now=now, stale_days=stale_days),
        "queues": queues_from_records(records, now=now, stale_days=stale_days),
        "disclaimer": "Read-only administrative indicators. Supply signals are transparent heuristics, not conclusions about player behavior.",
    }


def _price_refs(records: list[dict[str, Any]], item_ids: set, cut: int) -> dict[str, dict[str, float]]:
    """Median sale price per item (all sellers) within the window, split by single/stack, for markup indicators."""
    by: dict[tuple, list[int]] = {}
    for r in records:
        if r["sold_at"] and r["sold_at"] >= cut and r["item_id"] in item_ids and r["sale_price"]:
            by.setdefault((r["item_id"], "stack" if r["stack"] else "single"), []).append(int(r["sale_price"]))
            by.setdefault((r["item_id"], "all"), []).append(int(r["sale_price"]))
    out: dict[str, dict[str, float]] = {}
    for (iid, kind), v in by.items():
        out.setdefault(str(iid), {})[kind] = statistics.median(v)
        out[str(iid)][kind + "_n"] = len(v)
    return out


def seller_stats_from(records: list[dict[str, Any]], seller_id: int, now: int, days: int = 30) -> dict[str, Any]:
    """Pure: one seller's sales and sell-through over the last `days` days."""
    cut = now - days * 86400
    mine = [r for r in records if r["seller_id"] == seller_id]
    sold = sorted((r for r in mine if r["sold_at"] and r["sold_at"] >= cut), key=lambda r: -r["sold_at"])
    active = [r for r in mine if not r["sold_at"]]
    hrs = [(r["sold_at"] - r["listed_at"]) / 3600 for r in sold if r["listed_at"] and r["sold_at"] >= r["listed_at"]]
    return {"days": days, "sales": len(sold), "gil": sum(int(r["sale_price"]) for r in sold),
            "active": len(active), "sell_through": round(len(sold) / (len(sold) + len(active)) * 100, 1) if (sold or active) else None,
            "median_hours_to_sale": round(statistics.median(hrs), 1) if hrs else None,
            "refs": _price_refs(records, {r["item_id"] for r in active}, cut),
            "recent": [{"item_id": r["item_id"], "item_name": r["item_name"], "stack": r["stack"], "sale_price": int(r["sale_price"]),
                        "asking_price": int(r["asking_price"]), "sold_at": r["sold_at"], "buyer_name": r["buyer_name"]} for r in sold[:50]]}
