from workbench.server_admin.auction_house.economy_intelligence import trends_from_records

NOW = 1_000_000_000
DAY = 86400


def _rec(item, sold_days_ago, price, buyer="Bob", seller=1, listed_hours_before=2):
    sold = NOW - int(sold_days_ago * DAY)
    return {"auction_id": 0, "item_id": item, "item_name": f"item_{item}", "category_id": 1, "stack": False,
            "seller_id": seller, "seller_name": "S", "buyer_id": None, "buyer_name": buyer,
            "listed_at": sold - listed_hours_before * 3600, "asking_price": price, "sale_price": price, "sold_at": sold}


def test_current_vs_prior_window_and_deltas():
    recs = [_rec(1, 1, 200), _rec(1, 2, 220), _rec(1, 9, 100), _rec(1, 10, 100), _rec(2, 3, 500, buyer="Al")]
    t = trends_from_records(recs, now=NOW, days=7)
    assert t["current"]["sales"] == 3 and t["prior"]["sales"] == 2
    assert t["current"]["gil"] == 920 and t["current"]["unique_buyers"] == 2
    assert t["current"]["median_hours_to_sale"] == 2.0


def test_movers_flag_thin_evidence_and_skip_items_without_prior():
    recs = [_rec(1, 1, 200), _rec(1, 2, 220), _rec(1, 9, 100), _rec(1, 10, 100),
            _rec(3, 1, 900), _rec(3, 9, 100), _rec(2, 3, 500)]
    m = {x["item_id"]: x for x in trends_from_records(recs, now=NOW, days=7)["movers"]}
    assert set(m) == {1, 3}                       # item 2 has no prior sales
    assert m[1]["change_pct"] == 110.0 and m[1]["reliable"] is True
    assert m[3]["change_pct"] == 800.0 and m[3]["reliable"] is False


def _act(item, seller, listed_days_ago=1, price=100):
    return {"auction_id": 0, "item_id": item, "item_name": f"item_{item}", "category_id": 1, "stack": False,
            "seller_id": 1, "seller_name": seller, "buyer_id": None, "buyer_name": None,
            "listed_at": NOW - int(listed_days_ago * DAY), "asking_price": price, "sale_price": 0, "sold_at": 0}


def test_queues_and_concentration():
    from workbench.server_admin.auction_house.economy_intelligence import queues_from_records
    recs = ([_rec(1, 1, 50) for _ in range(4)]                                   # item 1: sells, nothing listed
            + [_act(2, "A") for _ in range(6)] + [_rec(2, 1, 50)]                 # item 2: 6 listed, 1 sold, one seller
            + [_act(3, "A", listed_days_ago=40), _act(3, "B", listed_days_ago=2)])  # item 3: stale, never sold
    q = queues_from_records(recs, now=NOW, stale_days=30)
    assert [r["item_id"] for r in q["needs_supply"]] == [1]
    assert [r["item_id"] for r in q["oversupplied"]] == [2]
    assert [r["item_id"] for r in q["stagnant"]] == [3]
    assert q["concentration"][0]["item_id"] == 2 and q["concentration"][0]["share_pct"] == 100.0
