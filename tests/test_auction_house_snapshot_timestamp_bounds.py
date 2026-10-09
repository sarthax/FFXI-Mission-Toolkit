"""Daily AH supply snapshots must not count future-dated activity."""
from workbench.server_admin.auction_house.snapshots import summarize


NOW = 1_700_000_000


def row(*, sold_at=0, listed_at=NOW, sale_price=0, asking_price=100):
    return {
        "item_id": 25, "item_name": "Test Item", "category_id": 2,
        "sold_at": sold_at, "listed_at": listed_at,
        "asking_price": asking_price, "sale_price": sale_price,
    }


def test_snapshot_excludes_future_sales_and_listings_from_rolling_week():
    records = [
        row(sold_at=NOW - 100, listed_at=NOW - 200, sale_price=90),
        row(sold_at=NOW + 3600, listed_at=NOW + 3600, sale_price=200),
        row(sold_at=0, listed_at=NOW + 3600),
        row(sold_at=0, listed_at=NOW - 100),
    ]
    result = summarize(records, NOW)
    assert result["sales_7d"] == 1
    assert result["gil_7d"] == 90
    assert result["listed_7d"] == 2
    assert result["active_listings"] == 2
    assert result["categories"][2]["sales_7d"] == 1
    assert result["items"][25]["sales_7d"] == 1


def test_snapshot_includes_window_boundaries():
    result = summarize([
        row(sold_at=NOW - 7 * 86400, listed_at=NOW - 7 * 86400, sale_price=100),
        row(sold_at=NOW, listed_at=NOW, sale_price=75),
    ], NOW)
    assert result["sales_7d"] == 2
    assert result["listed_7d"] == 2
