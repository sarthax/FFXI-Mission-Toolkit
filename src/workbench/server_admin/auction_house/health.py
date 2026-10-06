"""Read-only Auction House economy-health and anomaly diagnostics."""
from __future__ import annotations

from .schema import sellable_clause

_AI, _AIB = "i", "ib"

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

from .categories import category_metadata
from .service import AuctionHouseService, epoch_iso


def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def stale_listings(service: AuctionHouseService, *, days: int = 30, limit: int = 200) -> list[dict[str, Any]]:
    """Return oldest active listings at or beyond the requested age threshold."""
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    safe_days = max(1, min(int(days), 3650))
    safe_limit = max(1, min(int(limit), 1000))
    now = _now_epoch()
    cutoff = now - safe_days * 86400
    seller_name = f"ah.{qn(a['seller_name'])}" if a.get("seller_name") else "NULL"
    c = service.connection.cursor()
    try:
        c.execute(
            "SELECT "
            f"ah.{qn(a['id'])},ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},"
            f"ah.{qn(a['stack'])},ah.{qn(a['seller_id'])},{seller_name},"
            f"ah.{qn(a['listed_at'])},ah.{qn(a['asking_price'])} "
            "FROM `auction_house` ah JOIN `item_basic` i "
            f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
            f"WHERE ah.{qn(a['sold_at'])}=0 AND ah.{qn(a['listed_at'])}>0 "
            f"AND ah.{qn(a['listed_at'])}<=%s ORDER BY ah.{qn(a['listed_at'])} ASC LIMIT %s",
            (cutoff, safe_limit),
        )
        rows = []
        for r in c.fetchall() or []:
            listed_at = int(r[7] or 0)
            category = category_metadata(int(r[3] or 0))
            rows.append({
                "auction_id": int(r[0]), "item_id": int(r[1]), "item_name": str(r[2] or ""),
                "category_id": int(r[3] or 0), "category_path": category.path,
                "stack": bool(r[4]), "lot_type": "stack" if r[4] else "single",
                "seller_id": int(r[5] or 0), "seller_name": r[6],
                "listed_at": listed_at, "listed_at_iso": epoch_iso(listed_at),
                "age_days": round(max(0, now - listed_at) / 86400, 1),
                "asking_price": int(r[8] or 0),
            })
        return rows
    finally:
        c.close()


def market_movement(
    service: AuctionHouseService, *, recent_days: int = 7, baseline_days: int = 30,
    min_recent_sales: int = 2, min_baseline_sales: int = 3, limit: int = 200,
) -> list[dict[str, Any]]:
    """Compare recent price/volume against the preceding baseline window by item and lot type."""
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    recent_days = max(1, min(int(recent_days), 365))
    baseline_days = max(recent_days + 1, min(int(baseline_days), 3650))
    safe_limit = max(1, min(int(limit), 1000))
    now = _now_epoch()
    recent_cutoff = now - recent_days * 86400
    baseline_cutoff = now - baseline_days * 86400
    c = service.connection.cursor()
    try:
        c.execute(
            "SELECT "
            f"ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},ah.{qn(a['stack'])},"
            f"SUM(CASE WHEN ah.{qn(a['sold_at'])}>=%s THEN 1 ELSE 0 END),"
            f"AVG(CASE WHEN ah.{qn(a['sold_at'])}>=%s THEN ah.{qn(a['sale_price'])} END),"
            f"SUM(CASE WHEN ah.{qn(a['sold_at'])}>=%s AND ah.{qn(a['sold_at'])}<%s THEN 1 ELSE 0 END),"
            f"AVG(CASE WHEN ah.{qn(a['sold_at'])}>=%s AND ah.{qn(a['sold_at'])}<%s THEN ah.{qn(a['sale_price'])} END) "
            "FROM `auction_house` ah JOIN `item_basic` i "
            f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
            f"WHERE ah.{qn(a['sold_at'])}>=%s "
            f"GROUP BY ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},ah.{qn(a['stack'])}",
            (recent_cutoff, recent_cutoff, baseline_cutoff, recent_cutoff,
             baseline_cutoff, recent_cutoff, baseline_cutoff),
        )
        baseline_span_days = max(1, baseline_days - recent_days)
        rows = []
        for r in c.fetchall() or []:
            recent_sales, baseline_sales = int(r[4] or 0), int(r[6] or 0)
            if recent_sales < min_recent_sales or baseline_sales < min_baseline_sales:
                continue
            recent_avg, baseline_avg = float(r[5] or 0), float(r[7] or 0)
            if baseline_avg <= 0:
                continue
            price_change_pct = ((recent_avg - baseline_avg) / baseline_avg) * 100.0
            recent_daily, baseline_daily = recent_sales / recent_days, baseline_sales / baseline_span_days
            volume_change_pct = None if baseline_daily <= 0 else ((recent_daily - baseline_daily) / baseline_daily) * 100.0
            category = category_metadata(int(r[2] or 0))
            rows.append({
                "item_id": int(r[0]), "item_name": str(r[1] or ""),
                "category_id": int(r[2] or 0), "category_path": category.path,
                "stack": bool(r[3]), "lot_type": "stack" if r[3] else "single",
                "recent_days": recent_days, "baseline_days": baseline_span_days,
                "recent_sales": recent_sales, "baseline_sales": baseline_sales,
                "recent_average_price": round(recent_avg, 2), "baseline_average_price": round(baseline_avg, 2),
                "price_change_pct": round(price_change_pct, 2),
                "volume_change_pct": None if volume_change_pct is None else round(volume_change_pct, 2),
            })
        rows.sort(key=lambda row: abs(row["price_change_pct"]), reverse=True)
        return rows[:safe_limit]
    finally:
        c.close()


def participant_concentration(service: AuctionHouseService, *, days: int = 30, limit: int = 20) -> dict[str, Any]:
    """Measure seller/buyer concentration across completed sales in the requested window."""
    a, qn = service.schema.auction_columns, service.q
    safe_days = max(1, min(int(days), 3650))
    safe_limit = max(1, min(int(limit), 100))
    cutoff = _now_epoch() - safe_days * 86400
    c = service.connection.cursor()

    def _rank(identity_col: str, name_col: str | None, *, identity_is_name: bool = False) -> list[dict[str, Any]]:
        name_expr = qn(name_col) if name_col else "NULL"
        c.execute(
            f"SELECT {qn(identity_col)},{name_expr},COUNT(*),SUM({qn(a['sale_price'])}) "
            f"FROM `auction_house` WHERE {qn(a['sold_at'])}>=%s "
            f"GROUP BY {qn(identity_col)},{name_expr} ORDER BY SUM({qn(a['sale_price'])}) DESC LIMIT %s",
            (cutoff, safe_limit),
        )
        raw = c.fetchall() or []
        c.execute(f"SELECT SUM({qn(a['sale_price'])}) FROM `auction_house` WHERE {qn(a['sold_at'])}>=%s", (cutoff,))
        total_gil = int((c.fetchone() or (0,))[0] or 0)
        rows = []
        for r in raw:
            rows.append({
                "id": None if identity_is_name or r[0] is None else int(r[0] or 0),
                "name": str(r[0] or "") if identity_is_name else r[1],
                "sales": int(r[2] or 0), "gil": int(r[3] or 0),
                "gil_share_pct": None if total_gil <= 0 else round((int(r[3] or 0) / total_gil) * 100.0, 2),
            })
        return rows

    try:
        sellers = _rank(a["seller_id"], a.get("seller_name"))
        buyers = None
        buyer_identity_type = None
        if a.get("buyer_id"):
            buyers = _rank(a["buyer_id"], a.get("buyer_name"))
            buyer_identity_type = "id"
        elif a.get("buyer_name"):
            buyers = _rank(a["buyer_name"], None, identity_is_name=True)
            buyer_identity_type = "name"
        return {
            "window_days": safe_days, "sellers": sellers, "buyers": buyers,
            "buyer_identity_available": buyers is not None, "buyer_identity_type": buyer_identity_type,
        }
    finally:
        c.close()


def transaction_outliers(
    service: AuctionHouseService, *, days: int = 30, sample_limit: int = 20000,
    result_limit: int = 100, minimum_peer_sales: int = 5, ratio_threshold: float = 3.0,
) -> list[dict[str, Any]]:
    """Flag extreme sale prices relative to the item/lot median; this is only a review signal."""
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    safe_days = max(1, min(int(days), 3650))
    sample_limit = max(100, min(int(sample_limit), 100000))
    result_limit = max(1, min(int(result_limit), 1000))
    cutoff = _now_epoch() - safe_days * 86400
    seller_name = f"ah.{qn(a['seller_name'])}" if a.get("seller_name") else "NULL"
    buyer_name = f"ah.{qn(a['buyer_name'])}" if a.get("buyer_name") else "NULL"
    buyer_id = f"ah.{qn(a['buyer_id'])}" if a.get("buyer_id") else "NULL"
    c = service.connection.cursor()
    try:
        c.execute(
            "SELECT "
            f"ah.{qn(a['id'])},ah.{qn(a['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},"
            f"ah.{qn(a['stack'])},ah.{qn(a['seller_id'])},{seller_name},{buyer_id},{buyer_name},"
            f"ah.{qn(a['sale_price'])},ah.{qn(a['sold_at'])} "
            "FROM `auction_house` ah JOIN `item_basic` i "
            f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
            f"WHERE ah.{qn(a['sold_at'])}>=%s ORDER BY ah.{qn(a['sold_at'])} DESC LIMIT %s",
            (cutoff, sample_limit),
        )
        raw = c.fetchall() or []
        peers: dict[tuple[int, bool], list[int]] = defaultdict(list)
        for r in raw:
            peers[(int(r[1]), bool(r[4]))].append(int(r[9] or 0))
        rows = []
        for r in raw:
            prices = peers[(int(r[1]), bool(r[4]))]
            if len(prices) < minimum_peer_sales:
                continue
            med, price = float(median(prices)), int(r[9] or 0)
            if med <= 0 or price <= 0:
                continue
            ratio = price / med
            severity = max(ratio, med / price)
            if severity < ratio_threshold:
                continue
            category = category_metadata(int(r[3] or 0))
            rows.append({
                "auction_id": int(r[0]), "item_id": int(r[1]), "item_name": str(r[2] or ""),
                "category_id": int(r[3] or 0), "category_path": category.path,
                "stack": bool(r[4]), "lot_type": "stack" if r[4] else "single",
                "seller_id": int(r[5] or 0), "seller_name": r[6],
                "buyer_id": None if r[7] is None else int(r[7] or 0), "buyer_name": r[8],
                "sale_price": price, "peer_median_price": round(med, 2),
                "price_ratio_to_median": round(ratio, 3), "severity_ratio": round(severity, 3),
                "peer_sales": len(prices), "sold_at": int(r[10] or 0), "sold_at_iso": epoch_iso(r[10]),
                "signal": "high_price" if price > med else "low_price",
            })
        rows.sort(key=lambda row: row["severity_ratio"], reverse=True)
        return rows[:result_limit]
    finally:
        c.close()


def economy_health(
    service: AuctionHouseService, *, days: int = 30, stale_days: int = 30,
    recent_days: int = 7, baseline_days: int = 30,
) -> dict[str, Any]:
    """Bundle read-only economy-health diagnostics for the admin dashboard."""
    stale = stale_listings(service, days=stale_days, limit=100)
    movement = market_movement(service, recent_days=recent_days, baseline_days=baseline_days, limit=100)
    concentration = participant_concentration(service, days=days, limit=20)
    outliers = transaction_outliers(service, days=days, result_limit=100)
    return {
        "window_days": max(1, min(int(days), 3650)),
        "stale_threshold_days": max(1, min(int(stale_days), 3650)),
        "recent_days": max(1, min(int(recent_days), 365)),
        "baseline_days": max(int(recent_days) + 1, min(int(baseline_days), 3650)),
        "counts": {"stale_listings": len(stale), "market_movements": len(movement), "transaction_outliers": len(outliers)},
        "stale_listings": stale, "market_movements": movement,
        "participant_concentration": concentration, "transaction_outliers": outliers,
        "disclaimer": "Diagnostics are read-only signals for administrative review, not conclusions of abuse or manipulation.",
    }
