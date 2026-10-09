"""Anomaly evidence quality is independent of severity."""
from workbench.server_admin.auction_house.anomalies import anomalies_from

NOW = 1_700_000_000
DAY = 86400


def sale(ts, price):
    return dict(item_id=123, item_name="Potion", sold_at=ts, sale_price=price,
                listed_at=ts - 100, asking_price=price,
                seller_id=5, seller_name="Seller", auction_id=ts)


def test_price_shift_reports_limited_samples_without_downgrading_severity():
    earlier = [sale(NOW - (15 + i) * DAY, 100) for i in range(5)]
    recent = [sale(NOW - i * DAY, 1000) for i in range(2)]
    result = anomalies_from(earlier + recent, NOW)
    finding = next(f for f in result["findings"] if f["kind"] == "price_shift")
    assert finding["severity"] >= 1
    assert finding["evidence"]["quality"] == "limited"
    assert finding["evidence"]["historical_sales"] == 5
    assert finding["evidence"]["recent_sales"] == 2


def test_stronger_sample_quality_for_more_evidence():
    earlier = [sale(NOW - (15 + i) * DAY, 100) for i in range(20)]
    recent = [sale(NOW - i * 3600, 1000) for i in range(5)]
    result = anomalies_from(earlier + recent, NOW)
    finding = next(f for f in result["findings"] if f["kind"] == "price_shift")
    assert finding["evidence"]["quality"] == "strong"
    assert finding["evidence"]["historical_sales"] == 20
    assert finding["evidence"]["recent_sales"] == 5
