from pathlib import Path

from workbench.server_admin.auction_house import diagnostics as ah_diagnostics


class _FakeService:
    connection = object()

    def status(self):
        return {"family_hint": "legacy-dsp-topaz-compatible", "capabilities": ["categories", "item_search"]}

    def categories(self):
        raise RuntimeError("category probe failed")


def test_diagnostics_isolate_partial_failures_and_stay_read_only():
    originals = {
        name: getattr(ah_diagnostics, name)
        for name in (
            "search_items",
            "economy_summary",
            "stale_listings",
            "market_movement",
            "participant_concentration",
            "transaction_outliers",
            "probe_write_readiness",
        )
    }

    class _Probe:
        def as_dict(self):
            return {"database": "test", "lsb_listing_ready": False, "lsb_purchase_ready": False}

    try:
        ah_diagnostics.search_items = lambda service, query, limit=3: [{"item_id": 1, "name": "Potion"}]
        ah_diagnostics.economy_summary = lambda service, days=30: {"active_listings": 1, "sales": 2}
        ah_diagnostics.stale_listings = lambda service, days=30, limit=3: []
        ah_diagnostics.market_movement = lambda service, recent_days=7, baseline_days=30, limit=3: []
        ah_diagnostics.participant_concentration = lambda service, days=30, limit=3: {"sellers": [], "buyers": []}
        ah_diagnostics.transaction_outliers = lambda service, days=30, sample_limit=500, result_limit=3: []
        ah_diagnostics.probe_write_readiness = lambda connection: _Probe()

        payload = ah_diagnostics.run_read_only_diagnostics(_FakeService())
    finally:
        for name, value in originals.items():
            setattr(ah_diagnostics, name, value)

    assert payload["status"] == "degraded"
    assert payload["read_only"] is True
    assert payload["write_enabled"] is False
    assert payload["executor_enabled"] is False
    assert "categories" in payload["failed_checks"]
    assert "categories" in payload["critical_failed_checks"]
    checks = {row["name"]: row for row in payload["checks"]}
    assert checks["schema"]["ok"] is True
    assert checks["item_search"]["ok"] is True
    assert checks["categories"]["ok"] is False


def test_diagnostics_route_is_get_only_and_has_no_apply_path():
    source = Path("src/workbench/server_admin/auction_house/gui.py").read_text(encoding="utf-8")
    diagnostics_source = Path("src/workbench/server_admin/auction_house/diagnostics.py").read_text(encoding="utf-8")

    assert '@router.get("/diagnostics.json")' in source
    assert '@router.post("/diagnostics.json")' not in source
    assert "INSERT INTO" not in diagnostics_source
    assert "UPDATE `" not in diagnostics_source
    assert "DELETE FROM" not in diagnostics_source
    assert "executor_enabled\": False" in diagnostics_source


if __name__ == "__main__":
    test_diagnostics_isolate_partial_failures_and_stay_read_only()
    test_diagnostics_route_is_get_only_and_has_no_apply_path()
    print("Auction House diagnostics regression: PASS")
