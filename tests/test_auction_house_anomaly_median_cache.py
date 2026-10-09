"""Listing-price anomaly reference prices are reused for large active supplies."""
from workbench.server_admin.auction_house.anomalies import anomalies_from

NOW = 1_700_000_000
DAY = 86400


def record(item, auction, *, sold_at=0, price=100):
    return {"item_id": item, "item_name": "Item", "auction_id": auction,
            "sold_at": sold_at, "sale_price": price if sold_at else 0,
            "listed_at": NOW - DAY, "asking_price": price,
            "seller_id": 1, "seller_name": "Seller"}


def test_repeated_listings_use_same_historical_item_median():
    sales = [record(7, i, sold_at=NOW - (i + 10) * DAY, price=100) for i in range(8)]
    listings = [record(7, i + 100, price=400) for i in range(40)]
    result = anomalies_from(sales + listings, NOW)
    alerts = [r for r in result["findings"] if r["kind"] == "listing_overpriced"]
    assert len(alerts) == 40
    assert {r["baseline"] for r in alerts} == {100}


def test_unrelated_items_do_not_share_reference_prices():
    sales = [record(7, i, sold_at=NOW - (i + 10) * DAY, price=100) for i in range(8)]
    listings = [record(8, 900, price=400)]
    result = anomalies_from(sales + listings, NOW)
    assert not any(r["kind"].startswith("listing_") for r in result["findings"])
