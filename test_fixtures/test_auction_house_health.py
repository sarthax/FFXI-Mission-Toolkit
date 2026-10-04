from pathlib import Path
import ast


HEALTH = Path("src/workbench/server_admin/auction_house/health.py")
GUI = Path("src/workbench/server_admin/auction_house/gui.py")


def test_auction_house_health_module_is_read_only_and_parseable():
    source = HEALTH.read_text(encoding="utf-8")
    ast.parse(source)

    assert "def stale_listings" in source
    assert "def market_movement" in source
    assert "def participant_concentration" in source
    assert "def transaction_outliers" in source
    assert "def economy_health" in source
    assert "median(prices)" in source
    assert "buyer_identity_type" in source

    upper = source.upper()
    assert "INSERT INTO" not in upper
    assert "UPDATE `" not in upper
    assert "DELETE FROM" not in upper


def test_auction_house_health_route_is_get_only():
    source = GUI.read_text(encoding="utf-8")
    ast.parse(source)

    assert '@router.get("/health.json")' in source
    assert '@router.post("/health.json")' not in source
    assert "baseline_days must be greater than recent_days" in source
    assert "economy_health(" in source


if __name__ == "__main__":
    test_auction_house_health_module_is_read_only_and_parseable()
    test_auction_house_health_route_is_get_only()
    print("Auction House economy health regression: PASS")
