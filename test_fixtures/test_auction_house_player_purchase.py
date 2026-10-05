from pathlib import Path

from workbench.server_admin.auction_house.player_purchase import probe_player_purchase_engines


ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
    def fetchall(self):
        return list(self.rows)
    def close(self):
        pass


class _Connection:
    def __init__(self, rows):
        self.rows = rows
    def cursor(self):
        return _Cursor(self.rows)


def test_engine_probe_accepts_transactional_tables():
    result = probe_player_purchase_engines(_Connection([
        ("auction_house", "InnoDB"),
        ("char_inventory", "InnoDB"),
        ("delivery_box", "InnoDB"),
    ]))
    assert result.transactional is True
    assert result.blocking_tables == ()


def test_engine_probe_blocks_historical_myisam_inventory():
    result = probe_player_purchase_engines(_Connection([
        ("auction_house", "InnoDB"),
        ("char_inventory", "MyISAM"),
        ("delivery_box", "InnoDB"),
    ]))
    assert result.transactional is False
    assert result.blocking_tables == ("char_inventory",)


def test_engine_probe_blocks_missing_engine_evidence():
    result = probe_player_purchase_engines(_Connection([
        ("auction_house", "InnoDB"),
        ("delivery_box", "InnoDB"),
    ]))
    assert result.transactional is False
    assert "char_inventory" in result.blocking_tables


def test_player_purchase_executor_contains_required_fail_closed_guards():
    source = (ROOT / "src/workbench/server_admin/auction_house/player_purchase.py").read_text(encoding="utf-8")
    required = [
        "probe_player_purchase_engines",
        "Buyer must be offline",
        "Buyer Inventory is full",
        "Buyer does not have enough gil",
        "FOR UPDATE",
        "Buyer gil changed during purchase",
        "Seller settlement was not queued exactly once",
        "Buyer gil post-state verification failed",
        "Buyer inventory post-state verification failed",
        "Auction post-state verification failed",
        "connection.rollback()",
    ]
    for text in required:
        assert text in source


def test_player_purchase_api_and_listing_manager_are_wired():
    api = (ROOT / "src/workbench/server_admin/auction_house/player_purchase_api.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    js = (ROOT / "gui/static/auction_house_listing_manager.js").read_text(encoding="utf-8")
    assert '@router.get("/player-purchase-readiness.json")' in api
    assert '@router.post("/player-purchase.json")' in api
    assert "auction_house_player_purchase_router" in bridge
    assert "/auction-house/test-write/player-purchase.json" in js
    assert "Player Buy" in js
    assert "Player Preview" in js
