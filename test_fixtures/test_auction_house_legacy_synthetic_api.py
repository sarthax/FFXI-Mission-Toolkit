from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_listing_endpoint_is_explicit_and_test_scoped():
    api = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "legacy_test_api.py").read_text(encoding="utf-8")
    executor = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "legacy_test_executor.py").read_text(encoding="utf-8")

    assert '@router.post("/synthetic-listing.json")' in api
    assert "execute_legacy_test_synthetic_listing" in api
    assert "synthetic_supply_injected" in executor
    assert "listing_fee_charged" in executor
    assert "seller_inventory_removed" in executor
    assert '"supported_operations": ["price_change", "synthetic_listing"]' in executor
