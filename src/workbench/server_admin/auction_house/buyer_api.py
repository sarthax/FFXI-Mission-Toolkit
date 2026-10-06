"""Catalog (all AH-eligible items, listed or not) and buyer-side read endpoints for the console."""
from __future__ import annotations

from .schema import sellable_clause

from contextlib import contextmanager
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from workbench.runtime.legacy_settings import get_active_server_root

from .buyer_stats import buyer_detail_from, buyers_from
from .categories import category_metadata
from .factory import open_auction_house

router = APIRouter(tags=["Auction House Console"])


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


@router.get("/auction-house/console/catalog.json")
def console_catalog():
    """Every AH-eligible item with its live listing count and sale history (listed or not)."""
    try:
        with _context() as ctx:
            s = ctx.service
            i, a, qn = s.schema.item_columns, s.schema.auction_columns, s.q
            sql = (
                f"SELECT b.{qn(i['item_id'])}, b.{qn(i['name'])}, b.{qn(i['ah_category'])}, b.{qn(i['stack_size'])}, "
                f"COALESCE(st.active,0), COALESCE(st.sales,0), st.last_sold, st.avg_sale, st.min_ask "
                f"FROM `item_basic` b LEFT JOIN (SELECT `{a['item_id']}` iid, "
                f"SUM(CASE WHEN `{a['sold_at']}`=0 AND `{a['sale_price']}`=0 THEN 1 ELSE 0 END) active, "
                f"SUM(CASE WHEN `{a['sold_at']}`>0 THEN 1 ELSE 0 END) sales, "
                f"MAX(CASE WHEN `{a['sold_at']}`>0 THEN `{a['sold_at']}` END) last_sold, "
                f"AVG(CASE WHEN `{a['sold_at']}`>0 THEN `{a['sale_price']}` END) avg_sale, "
                f"MIN(CASE WHEN `{a['sold_at']}`=0 THEN `{a['asking_price']}` END) min_ask "
                f"FROM `auction_house` GROUP BY `{a['item_id']}`) st ON st.iid=b.{qn(i['item_id'])} "
                f"WHERE {sellable_clause(i, qn, 'b')} ORDER BY b.{qn(i['name'])}"
            )
            cur = s.connection.cursor()
            try:
                cur.execute(sql)
                rows = list(cur.fetchall() or [])
            finally:
                cur.close()
            out = []
            for r in rows:
                cat = category_metadata(int(r[2] or 0))
                out.append({"item_id": int(r[0]), "item_name": str(r[1] or ""), "category_id": int(r[2] or 0), "category_path": cat.path,
                            "stack_size": max(1, int(r[3] or 1)), "listings": int(r[4] or 0), "sales": int(r[5] or 0),
                            "last_sold_at": int(r[6] or 0) or None, "avg_sale": None if r[7] is None else round(float(r[7])),
                            "min_price": None if r[8] is None else int(r[8])})
            return JSONResponse({"generated_at": int(time.time()), "count": len(out), "rows": out})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _records(days: int):
    from .economy_intelligence import _MAX_SAMPLE_ROWS, _load_records, _now_epoch
    with _context() as ctx:
        records, _ = _load_records(ctx.service, days=days, sample_limit=_MAX_SAMPLE_ROWS)
    return records, _now_epoch()


@router.get("/auction-house/console/buyers.json")
def console_buyers(days: int = Query(default=30, ge=1, le=365)):
    try:
        records, now = _records(days)
        return JSONResponse(buyers_from(records, now, days))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/auction-house/console/buyer.json")
def console_buyer(buyer: str = Query(min_length=1), days: int = Query(default=30, ge=1, le=365)):
    try:
        records, now = _records(days)
        return JSONResponse(buyer_detail_from(records, buyer, now, days))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
