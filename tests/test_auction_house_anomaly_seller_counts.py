"""Repeated seller activity keeps accurate flood evidence counts."""
from workbench.server_admin.auction_house.anomalies import anomalies_from

NOW = 1_700_000_000
DAY = 86400


def listing(idx, when):
    return {"item_id": 10, "item_name": "Potion", "auction_id": idx,
            "sold_at": 0, "sale_price": 0, "listed_at": when,
            "asking_price": 100, "seller_id": 77, "seller_name": "Seller"}


def test_seller_flood_keeps_historical_and_recent_evidence_counts():
    earlier = [listing(i, NOW - (10 + i) * DAY) for i in range(5)]
    recent = [listing(100 + i, NOW - i * 100) for i in range(15)]
    report = anomalies_from(earlier + recent, NOW)
    flood = next(x for x in report["findings"] if x["kind"] == "seller_flood")
    assert flood["evidence"]["historical_listings"] == 5
    assert flood["evidence"]["recent_listings"] == 15
    assert flood["evidence"]["quality"] == "limited"
