from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import player_listing as pl

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self._rows = []

    def execute(self, sql, params=()):
        if "information_schema`.`TABLES" in sql:
            self._rows = list(self.rows)
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return _Cursor(self.rows)


def test_player_listing_engine_probe_requires_transactional_inventory():
    ready = pl.probe_player_listing_engines(_Connection([
        ("auction_house", "InnoDB"),
        ("char_inventory", "InnoDB"),
    ]))
    assert ready.transactional is True
    assert ready.blocking_tables == ()

    blocked = pl.probe_player_listing_engines(_Connection([
        ("auction_house", "InnoDB"),
        ("char_inventory", "MyISAM"),
    ]))
    assert blocked.transactional is False
    assert blocked.blocking_tables == ("char_inventory",)


def test_player_listing_executor_fails_closed_on_myisam(monkeypatch, tmp_path):
    service = SimpleNamespace(
        schema=SimpleNamespace(family_hint="legacy-dsp-topaz-compatible"),
        connection=object(),
    )
    monkeypatch.setattr(pl, "evaluate_legacy_test_write_gate", lambda **kw: SimpleNamespace(ready=True, issues=[]))
    monkeypatch.setattr(pl, "load_active_legacy_policy", lambda **kw: SimpleNamespace(
        policy_ready=True,
        policy=SimpleNamespace(base_fee_single=1, base_fee_stacks=4, tax_rate_single=1.0, tax_rate_stacks=0.5, max_fee=10000, list_limit=7),
        issues=[], source_path="conf/map.conf", policy_fingerprint="abc",
    ))
    monkeypatch.setattr(pl, "probe_player_listing_engines", lambda connection: pl.ListingEngineProbe(
        engines={"auction_house": "InnoDB", "char_inventory": "MyISAM"},
        transactional=False,
        blocking_tables=("char_inventory",),
    ))
    with pytest.raises(pl.LegacyTestExecutionBlocked, match="char_inventory"):
        pl.execute_legacy_test_player_listing(
            service=service,
            server_root=tmp_path,
            environment={"name": "TOPAZ Test", "family": "topaz", "environment": "test", "enabled": True, "is_active": True},
            seller_id=7,
            inventory_slot=3,
            item_id=100,
            price=9000,
            stack=False,
            confirmation="TOPAZ Test",
            feature_enabled=True,
        )


def test_player_listing_contract_is_exact_slot_and_source_policy_backed():
    source = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "player_listing.py").read_text(encoding="utf-8")
    assert "load_active_legacy_policy" in source
    assert "legacy_listing_fee" in source
    assert "inventory_slot" in source
    assert "FOR UPDATE" in source
    assert "current_quantity != stack_size" in source
    assert "policy.list_limit" in source
    assert "Seller must be offline" in source
    assert "transactional auction_house and char_inventory" in source


def test_player_listing_api_is_mounted_and_narrow():
    api = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "player_listing_api.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "integration.py").read_text(encoding="utf-8")
    assert '@router.get("/player-listing-readiness.json")' in api
    assert '@router.post("/player-listing.json")' in api
    assert "execute_legacy_test_player_listing" in api
    assert "auction_house_player_listing_router" in bridge
    assert "payload.get(\"sql\")" not in api
