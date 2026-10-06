from workbench.server_admin.auction_house.snapshots import summarize

NOW = 1_000_000_000
DAY = 86400


def _r(item, cat, sold_days=None, price=100, listed_days=1):
    return {"item_id": item, "item_name": f"i{item}", "category_id": cat, "asking_price": price,
            "sale_price": price if sold_days is not None else 0,
            "listed_at": NOW - int(listed_days * DAY), "sold_at": NOW - int(sold_days * DAY) if sold_days is not None else 0}


def test_summarize_supply_and_sell_through():
    recs = [_r(1, 5), _r(1, 5), _r(2, 6, price=300), _r(1, 5, sold_days=1), _r(2, 6, sold_days=2, price=50)]
    s = summarize(recs, NOW)
    assert s["active_listings"] == 3 and s["active_gil"] == 500 and s["active_items"] == 2
    assert s["sales_7d"] == 2 and s["gil_7d"] == 150
    assert s["sell_through_7d"] == 40.0
    assert s["categories"][5]["active"] == 2 and s["items"][1]["sales_7d"] == 1


def test_summarize_empty():
    assert summarize([], NOW)["sell_through_7d"] is None


def test_baselines_building_then_flagging():
    from workbench.server_admin.auction_house.snapshots import baselines_from_series
    mk = lambda v: {"active_listings": v, "active_gil": 1000, "sales_7d": 10, "sell_through_7d": 50.0}
    few = baselines_from_series([mk(100)] * 3)
    assert few["metrics"]["active_listings"]["status"] == "building"
    series = [mk(100 + (i % 3)) for i in range(10)] + [mk(180)]
    m = baselines_from_series(series)["metrics"]
    assert m["active_listings"]["status"] == "high" and m["active_listings"]["baseline"] == 101
    assert m["active_gil"]["status"] == "normal"
