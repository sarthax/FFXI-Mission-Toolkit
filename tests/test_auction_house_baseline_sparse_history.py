"""Auction House baseline reliability for sparse and nonnegative metrics."""
from workbench.server_admin.auction_house.snapshots import baselines_from_series


def row(day, **overrides):
    result = {"day": day, "active_listings": 1, "active_gil": 2,
              "sales_7d": 0, "sell_through_7d": 0.0}
    result.update(overrides)
    return result


def test_baseline_uses_available_points_per_metric():
    series = [row(str(i), active_gil=None if i < 3 else 2) for i in range(8)]
    result = baselines_from_series(series)["metrics"]
    assert result["active_listings"]["history_points"] == 7
    assert result["active_listings"]["status"] == "normal"
    assert result["active_gil"]["history_points"] == 4
    assert result["active_gil"]["points_needed"] == 3
    assert result["active_gil"]["status"] == "building"


def test_baseline_lower_bound_cannot_be_negative():
    series = [row(str(i), active_listings=0) for i in range(7)]
    series.append(row("latest", active_listings=1))
    result = baselines_from_series(series)["metrics"]["active_listings"]
    assert result["low"] == 0
    assert result["status"] == "high"
    assert result["points_needed"] == 0


def test_empty_baseline_retains_no_metrics():
    result = baselines_from_series([])
    assert result["points"] == 0
    assert result["metrics"] == {}
