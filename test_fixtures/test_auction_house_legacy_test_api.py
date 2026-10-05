from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_test_write_api_is_narrow_and_mounted():
    api = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "legacy_test_api.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "integration.py").read_text(encoding="utf-8")

    assert 'prefix="/auction-house/test-write"' in api
    assert '@router.post("/readiness.json")' in api
    assert '@router.post("/price-change.json")' in api
    assert "execute_legacy_test_price_change" in api
    for router_name in (
        "auction_house_router",
        "auction_house_test_write_router",
        "auction_house_listing_router",
        "auction_house_admin_buy_router",
    ):
        assert router_name in bridge


def test_legacy_test_write_api_exposes_no_free_form_sql_surface():
    api = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "legacy_test_api.py").read_text(encoding="utf-8")
    assert 'payload.get("sql")' not in api
    assert "cursor.execute" not in api
    assert "auction_id" in api
    assert "expected_price" in api
    assert "new_price" in api
    assert "confirmation" in api
