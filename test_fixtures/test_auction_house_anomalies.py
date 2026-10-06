from workbench.server_admin.auction_house.anomalies import anomalies_from

NOW = 10_000_000
D = 86400


def rec(item, price=0, sold_days=None, ask=0, seller=1, listed_days=1, aid=0):
    return {"auction_id": aid, "item_id": item, "item_name": f"I{item}", "category_id": 1, "stack": False, "seller_id": seller,
            "seller_name": f"S{seller}", "buyer_id": None, "buyer_name": None, "listed_at": NOW - listed_days * D,
            "asking_price": ask or price, "sale_price": price if sold_days is not None else 0,
            "sold_at": NOW - sold_days * D if sold_days is not None else 0}


def history(item, price, n=8):
    return [rec(item, price + i, sold_days=20 + i) for i in range(n)]


def kinds(res):
    return {f["kind"] for f in res["findings"]}


def test_price_shift_detected_and_stable_item_ignored():
    rs = history(1, 1000) + [rec(1, 3000, sold_days=1), rec(1, 3100, sold_days=2)]
    rs += history(2, 1000) + [rec(2, 1010, sold_days=1), rec(2, 990, sold_days=2)]
    res = anomalies_from(rs, NOW)
    shifts = [f for f in res["findings"] if f["kind"] == "price_shift"]
    assert [f["item_id"] for f in shifts] == [1]
    assert shifts[0]["change_pct"] > 100


def test_listing_far_from_median_flagged_both_ways():
    rs = history(3, 1000) + [rec(3, ask=9000, aid=1), rec(3, ask=100, aid=2), rec(3, ask=1100, aid=3)]
    res = anomalies_from(rs, NOW)
    assert kinds(res) >= {"listing_overpriced", "listing_underpriced"}
    assert {f["auction_id"] for f in res["findings"] if f["kind"].startswith("listing")} == {1, 2}


def test_too_little_history_never_flags():
    rs = [rec(4, 1000, sold_days=20), rec(4, 5000, sold_days=1), rec(4, 5000, sold_days=2), rec(4, ask=99999)]
    assert anomalies_from(rs, NOW)["count"] == 0


def test_seller_flood():
    rs = [rec(5, ask=100, seller=7, listed_days=30 + i, aid=i) for i in range(6)]
    rs += [rec(5, ask=100, seller=7, listed_days=1, aid=100 + i) for i in range(30)]
    assert "seller_flood" in kinds(anomalies_from(rs, NOW))
