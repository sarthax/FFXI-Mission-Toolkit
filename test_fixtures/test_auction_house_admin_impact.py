from workbench.server_admin.auction_house.admin_impact import impact_from

NOW = 1_000_000_000
DAY = 86400


def _sale(item, days_ago, price):
    return {"item_id": item, "item_name": "x", "sold_at": NOW - int(days_ago * DAY), "sale_price": price}


def _row(op, days_ago, item=None, status="committed"):
    from datetime import datetime, timezone
    return {"operation": op, "status": status, "item_id": item,
            "occurred_at_utc": datetime.fromtimestamp(NOW - int(days_ago * DAY), timezone.utc).isoformat()}


def test_before_after_and_filtering():
    recs = [_sale(1, 10, 100), _sale(1, 8, 100), _sale(1, 3, 150), _sale(1, 2, 150)]
    ev = impact_from(recs, [_row("admin_buy", 5, 1), _row("restock", 5, 1, status="blocked"), _row("market_seed", 4)], NOW)
    assert [e["operation"] for e in ev] == ["market_seed", "admin_buy"]
    buy = ev[1]
    assert buy["change_pct"] == 50.0 and buy["sales_before"] == 2 and buy["sales_after"] == 2
    assert ev[0]["change_pct"] is None
