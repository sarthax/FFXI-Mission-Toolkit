"""Anomaly detection ignores future evidence and rejects overlapping windows."""
import pytest
from workbench.server_admin.auction_house.anomalies import anomalies_from

NOW = 1_700_000_000
DAY = 86400


def sale(i, time, price=100):
    return {"item_id": i, "item_name": "Potion", "sold_at": time, "sale_price": price,
            "listed_at": time - 100, "asking_price": price, "seller_id": 3,
            "seller_name": "Seller", "auction_id": time}


def test_future_sales_cannot_inflate_volume_or_price_anomaly():
    history = [sale(1, NOW - (20 + i) * DAY) for i in range(8)]
    future = [sale(1, NOW + (i + 1) * 100, 10000) for i in range(20)]
    result = anomalies_from(history + future, NOW)
    assert not any(f["kind"] in {"volume_spike", "price_shift"} for f in result["findings"])


def test_future_listings_cannot_trigger_seller_flood():
    earlier = [sale(1, NOW - 15 * DAY)]
    future = [dict(sale(2, NOW + i + 1), sold_at=0) for i in range(20)]
    result = anomalies_from(earlier + future, NOW)
    assert not any(f["kind"] == "seller_flood" for f in result["findings"])


@pytest.mark.parametrize("days,history_days", [(0, 60), (-1, 60), (7, 7), (8, 7)])
def test_invalid_anomaly_windows_rejected(days, history_days):
    with pytest.raises(ValueError):
        anomalies_from([], NOW, days=days, history_days=history_days)
