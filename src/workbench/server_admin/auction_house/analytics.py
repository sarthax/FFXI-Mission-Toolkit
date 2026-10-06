"""Read-only catalog and economy analytics layered over AuctionHouseService."""
from __future__ import annotations

from .schema import sellable_clause

_AI, _AIB = "i", "ib"

from datetime import datetime, timezone
from typing import Any

from .categories import category_metadata
from .service import AuctionHouseService, epoch_iso


def search_items(service: AuctionHouseService, query: str = "", *, category_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    i, a = service.schema.item_columns, service.schema.auction_columns
    qn = service.q
    safe_limit = max(1, min(int(limit), 500))
    where = [sellable_clause(i, qn, "i")]
    params: list[Any] = []
    term = str(query or "").strip()
    if term:
        if term.isdigit():
            where.append(f"(i.{qn(i['item_id'])}=%s OR i.{qn(i['name'])} LIKE %s)")
            params += [int(term), f"%{term}%"]
        else:
            where.append(f"i.{qn(i['name'])} LIKE %s")
            params.append(f"%{term}%")
    if category_id is not None:
        where.append(f"i.{qn(i['ah_category'])}=%s")
        params.append(int(category_id))
    params.append(safe_limit)
    sql = (
        f"SELECT i.{qn(i['item_id'])}, i.{qn(i['name'])}, i.{qn(i['ah_category'])}, i.{qn(i['stack_size'])}, "
        f"SUM(CASE WHEN ah.{qn(a['sold_at'])}=0 THEN 1 ELSE 0 END), "
        f"SUM(CASE WHEN ah.{qn(a['sold_at'])}>0 THEN 1 ELSE 0 END), "
        f"MAX(CASE WHEN ah.{qn(a['sold_at'])}>0 THEN ah.{qn(a['sold_at'])} ELSE 0 END), "
        f"AVG(CASE WHEN ah.{qn(a['sold_at'])}>0 THEN ah.{qn(a['sale_price'])} ELSE NULL END) "
        "FROM `item_basic` i LEFT JOIN `auction_house` ah "
        f"ON ah.{qn(a['item_id'])}=i.{qn(i['item_id'])} WHERE {' AND '.join(where)} "
        f"GROUP BY i.{qn(i['item_id'])},i.{qn(i['name'])},i.{qn(i['ah_category'])},i.{qn(i['stack_size'])} "
        f"ORDER BY i.{qn(i['name'])} LIMIT %s"
    )
    c = service.connection.cursor()
    try:
        c.execute(sql, tuple(params))
        rows = []
        for r in c.fetchall() or []:
            category_id_value = int(r[2] or 0)
            category = category_metadata(category_id_value)
            rows.append({
                "item_id": int(r[0]), "name": str(r[1] or ""), "category_id": category_id_value,
                "category_group": category.group, "category_label": category.label, "category_path": category.path,
                "stack_size": max(1, int(r[3] or 1)), "active_listings": int(r[4] or 0),
                "historical_sales": int(r[5] or 0), "last_sold_at": int(r[6] or 0) or None,
                "last_sold_at_iso": epoch_iso(r[6]),
                "average_sale_price": None if r[7] is None else round(float(r[7]), 2),
            })
        return rows
    finally:
        c.close()


def price_trends(service: AuctionHouseService, item_id: int, *, days: int = 30) -> list[dict[str, Any]]:
    """Return daily sale bands split by single/stack lot type.

    FFXI single and stack auctions have materially different lot prices, so combining them into a
    single average is misleading. ``average_unit_price`` normalizes a stack sale by the item's
    configured stack size while retaining the actual lot-price band for administrative review.
    """
    a, i, qn = service.schema.auction_columns, service.schema.item_columns, service.q
    safe_days = max(1, min(int(days), 3650))
    cutoff = int(datetime.now(timezone.utc).timestamp()) - safe_days * 86400
    stack_size = f"GREATEST(i.{qn(i['stack_size'])}, 1)"
    unit_expr = (
        f"CASE WHEN ah.{qn(a['stack'])}=1 THEN ah.{qn(a['sale_price'])}/{stack_size} "
        f"ELSE ah.{qn(a['sale_price'])} END"
    )
    c = service.connection.cursor()
    try:
        c.execute(
            f"SELECT DATE(FROM_UNIXTIME(ah.{qn(a['sold_at'])})),ah.{qn(a['stack'])},COUNT(*),"
            f"AVG(ah.{qn(a['sale_price'])}),MIN(ah.{qn(a['sale_price'])}),MAX(ah.{qn(a['sale_price'])}),"
            f"AVG({unit_expr}) FROM `auction_house` ah JOIN `item_basic` i "
            f"ON i.{qn(i['item_id'])}=ah.{qn(a['item_id'])} AND {sellable_clause(i, qn, _AI)} "
            f"WHERE ah.{qn(a['item_id'])}=%s AND ah.{qn(a['sold_at'])}>=%s GROUP BY 1,2 ORDER BY 1,2",
            (int(item_id), cutoff),
        )
        return [{
            "day": r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]),
            "stack": bool(r[1]), "lot_type": "stack" if r[1] else "single", "sales": int(r[2]),
            "average_price": round(float(r[3]), 2), "min_price": int(r[4]), "max_price": int(r[5]),
            "average_unit_price": round(float(r[6]), 2),
        } for r in c.fetchall() or []]
    finally:
        c.close()


def economy_summary(service: AuctionHouseService, *, days: int = 30) -> dict[str, Any]:
    a, qn = service.schema.auction_columns, service.q
    safe_days = max(1, min(int(days), 3650))
    cutoff = int(datetime.now(timezone.utc).timestamp()) - safe_days * 86400
    c = service.connection.cursor()
    try:
        c.execute(
            f"SELECT SUM({qn(a['sold_at'])}=0),SUM({qn(a['sold_at'])}>=%s),"
            f"SUM(CASE WHEN {qn(a['sold_at'])}>=%s THEN {qn(a['sale_price'])} ELSE 0 END),"
            f"COUNT(DISTINCT CASE WHEN {qn(a['sold_at'])}>=%s THEN {qn(a['seller_id'])} END) FROM `auction_house`",
            (cutoff, cutoff, cutoff),
        )
        r = c.fetchone() or (0, 0, 0, 0)
        out = {"window_days": safe_days, "active_listings": int(r[0] or 0), "sales": int(r[1] or 0),
               "gil_transacted": int(r[2] or 0), "unique_sellers": int(r[3] or 0)}
        buyer = a.get("buyer_id") or a.get("buyer_name")
        if buyer:
            c.execute(
                f"SELECT COUNT(DISTINCT {qn(buyer)}) FROM `auction_house` WHERE {qn(a['sold_at'])}>=%s",
                (cutoff,),
            )
            out["unique_buyers"] = int((c.fetchone() or (0,))[0] or 0)
        else:
            out["unique_buyers"] = None
        return out
    finally:
        c.close()
