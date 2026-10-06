from workbench.server_admin.auction_house.economy_intelligence import seller_stats_from

NOW, DAY = 1_000_000_000, 86400


def _r(seller, sold_days_ago=None, price=100):
    sold = NOW - int(sold_days_ago * DAY) if sold_days_ago is not None else 0
    return {"item_id": 1, "item_name": "x", "stack": False, "seller_id": seller, "buyer_name": "B",
            "listed_at": (sold or NOW) - 7200, "asking_price": price, "sale_price": price if sold else 0, "sold_at": sold}


def test_seller_stats_scoped_to_seller_and_window():
    recs = [_r(1, 1), _r(1, 2, 300), _r(1, 40), _r(1), _r(2, 1)]
    s = seller_stats_from(recs, 1, NOW, 30)
    assert s["sales"] == 2 and s["gil"] == 400 and s["active"] == 1
    assert s["sell_through"] == 66.7 and s["median_hours_to_sale"] == 2.0
    assert s["recent"][0]["sold_at"] > s["recent"][1]["sold_at"]


def test_price_refs_split_by_stack():
    recs = [_r(2, 1, 100), _r(2, 2, 300), _r(2, 3, 200), _r(1)]
    s = seller_stats_from(recs, 1, NOW, 30)
    assert s["refs"]["1"]["single"] == 200 and s["refs"]["1"]["single_n"] == 3
