from pathlib import Path

from workbench.server_admin.auction_house.economy_intelligence import (
    category_intelligence_from_records,
    seller_intelligence_from_records,
)

NOW = 10_000_000
DAY = 86400


def row(*, auction_id, item_id, item_name, category_id, seller_id, seller_name, listed_days_ago, ask, sold_days_ago=None, sale=0):
    return {
        "auction_id": auction_id,
        "item_id": item_id,
        "item_name": item_name,
        "category_id": category_id,
        "stack": False,
        "seller_id": seller_id,
        "seller_name": seller_name,
        "buyer_id": None,
        "buyer_name": None,
        "listed_at": NOW - listed_days_ago * DAY,
        "asking_price": ask,
        "sale_price": sale,
        "sold_at": 0 if sold_days_ago is None else NOW - sold_days_ago * DAY,
    }


def test_seller_metrics_median_buckets_and_sell_through():
    records = [
        row(auction_id=1,item_id=10,item_name="A",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=2,ask=100),
        row(auction_id=2,item_id=11,item_name="B",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=20,ask=300),
        row(auction_id=3,item_id=12,item_name="C",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=45,ask=500),
        row(auction_id=4,item_id=13,item_name="D",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=100,ask=700),
        row(auction_id=5,item_id=10,item_name="A",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=12,ask=90,sold_days_ago=5,sale=120),
        row(auction_id=6,item_id=10,item_name="A",category_id=1,seller_id=7,seller_name="Alice",listed_days_ago=14,ask=110,sold_days_ago=3,sale=180),
    ]
    result = seller_intelligence_from_records(records, now=NOW, stale_days=30)[0]
    assert result["active_listings"] == 4
    assert result["active_asking_value"] == 1600
    assert result["sold_count"] == 2
    assert result["sold_gil"] == 300
    assert result["median_asking_price"] == 400.0
    assert result["median_sale_price"] == 150.0
    assert result["aging_buckets"] == {"lt_7d": 1, "7_30d": 1, "30_90d": 1, "90d_plus": 1}
    assert result["stale_active_count"] == 2
    assert result["sell_through_pct"] == 33.33


def test_category_undersupplied_signal_is_transparent():
    records = [
        row(auction_id=1,item_id=10,item_name="A",category_id=5,seller_id=1,seller_name="One",listed_days_ago=2,ask=100),
        row(auction_id=2,item_id=11,item_name="B",category_id=5,seller_id=2,seller_name="Two",listed_days_ago=3,ask=200),
    ]
    for n in range(5):
        records.append(row(auction_id=10+n,item_id=10,item_name="A",category_id=5,seller_id=1,seller_name="One",listed_days_ago=10,ask=90,sold_days_ago=n+1,sale=100+n))
    result = category_intelligence_from_records(records, now=NOW, stale_days=30)[0]
    assert result["active_listings"] == 2
    assert result["sold_count"] == 5
    assert result["supply_signal"] == "undersupplied"
    assert "<=2 active" in result["signal_basis"]["heuristic"]


def test_category_stale_or_oversupplied_signal():
    records = []
    for n in range(10):
        records.append(row(auction_id=n+1,item_id=100+n,item_name=f"Item {n}",category_id=9,seller_id=1,seller_name="One",listed_days_ago=45+n,ask=1000))
    records.append(row(auction_id=20,item_id=100,item_name="Item 0",category_id=9,seller_id=1,seller_name="One",listed_days_ago=50,ask=1000,sold_days_ago=2,sale=800))
    result = category_intelligence_from_records(records, now=NOW, stale_days=30)[0]
    assert result["stale_active_count"] == 10
    assert result["supply_signal"] == "stale_or_oversupplied"


def test_empty_inputs_are_safe():
    assert seller_intelligence_from_records([], now=NOW) == []
    assert category_intelligence_from_records([], now=NOW) == []


def test_economy_page_and_routes_are_mounted():
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    template = Path("gui/templates/auction_house_economy.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_economy.js").read_text(encoding="utf-8")
    console = Path("gui/static/auction_house_console.js").read_text(encoding="utf-8")
    api = Path("src/workbench/server_admin/auction_house/economy_api.py").read_text(encoding="utf-8")
    core = Path("src/workbench/server_admin/auction_house/economy_intelligence.py").read_text(encoding="utf-8")
    assert "auction_house_economy_router" in integration
    assert "/auction-house/economy" in console
    assert "/auction-house/economy.json" in api
    assert "/auction-house/economy.json" in script
    assert "sample_limit" in api and "50000" in api
    assert "LIMIT %s" in core
    assert "Economy Intelligence" in template
