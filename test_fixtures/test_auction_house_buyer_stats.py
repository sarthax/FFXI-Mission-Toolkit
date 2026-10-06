from workbench.server_admin.auction_house.buyer_stats import buyer_detail_from, buyers_from

NOW = 1_000_000_000
DAY = 86400


def rec(aid, buyer, price, item=1, age_days=1, seller=10, stack=False, buyer_id=None):
    return {"auction_id": aid, "item_id": item, "item_name": f"item{item}", "stack": stack, "seller_id": seller,
            "seller_name": f"S{seller}", "buyer_id": buyer_id, "buyer_name": buyer, "listed_at": NOW - (age_days + 1) * DAY,
            "asking_price": price, "sale_price": price, "sold_at": NOW - age_days * DAY}


BASE = [rec(1, "Ann", 100), rec(2, "Bob", 100), rec(3, "Cy", 100), rec(4, "Ann", 300)]  # median of 100,100,100,300 = 100


def test_buyers_keyed_by_name_case_insensitive():
    out = buyers_from(BASE + [rec(5, "ann", 100)], NOW, 30)
    assert out["count"] == 3
    ann = next(b for b in out["buyers"] if b["buyer_key"] == "ann")
    assert ann["purchases"] == 3 and ann["spent"] == 500


def test_overpaid_flagged_against_median():
    ann = next(b for b in buyers_from(BASE, NOW, 30)["buyers"] if b["buyer_key"] == "ann")
    assert ann["overpaid_count"] == 1 and ann["overpaid_gil"] == 200


def test_no_reference_when_fewer_than_three_sales():
    out = buyers_from([rec(1, "Ann", 100), rec(2, "Bob", 900)], NOW, 30)
    assert all(b["overpaid_count"] == 0 and b["avg_markup_pct"] is None for b in out["buyers"])


def test_window_excludes_old_sales_and_unnamed_buyers():
    out = buyers_from(BASE + [rec(6, "Old", 100, age_days=60), rec(7, "", 100)], NOW, 30)
    assert {b["buyer_key"] for b in out["buyers"]} == {"ann", "bob", "cy"}


def test_id_fallback_when_name_missing():
    out = buyers_from([rec(1, "", 100, buyer_id=7)], NOW, 30)
    assert out["buyers"][0]["buyer_key"] == "#7"


def test_stack_and_single_use_separate_references():
    recs = [rec(i, "A", 100) for i in range(3)] + [rec(9, "B", 5000, stack=True)]
    b = next(x for x in buyers_from(recs, NOW, 30)["buyers"] if x["buyer_key"] == "b")
    assert b["overpaid_count"] == 0


def test_detail_rows_and_totals():
    d = buyer_detail_from(BASE, "ANN", NOW, 30)
    assert d["purchases"] == 2 and d["spent"] == 400 and d["overpaid_count"] == 1 and d["overpaid_gil"] == 200
    over = next(r for r in d["rows"] if r["price"] == 300)
    assert over["median"] == 100 and over["overpaid_by"] == 200 and over["markup_pct"] == 200.0
    assert d["top_items"][0]["count"] == 2 and d["top_sellers"][0]["seller_id"] == 10


def test_detail_unknown_buyer_is_empty():
    d = buyer_detail_from(BASE, "nobody", NOW, 30)
    assert d["purchases"] == 0 and d["rows"] == []
