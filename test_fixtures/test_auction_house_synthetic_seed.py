from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import synthetic_seed as seed

ROOT = Path(__file__).resolve().parents[1]


class _Cursor:
    def __init__(self):
        self._rows = []

    def execute(self, sql, params=()):
        if "FROM `item_basic`" in sql:
            category_id, limit = map(int, params)
            assert category_id == 42
            self._rows = [
                (100, "Potion", 12, 42),
                (101, "Ether", 1, 42),
                (102, "Hi-Potion", 12, 42),
            ][:limit]
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _Service:
    schema = SimpleNamespace(item_columns={
        "item_id": "itemid", "name": "name", "stack_size": "stackSize", "ah_category": "aH"
    }, family_hint="legacy-dsp-topaz-compatible")

    def __init__(self):
        self.connection = SimpleNamespace(cursor=lambda: _Cursor())

    def character_snapshot(self, char_id):
        return {"char_id": 7, "char_name": "Seeder"} if int(char_id) == 7 else None


def _env():
    return {"name": "TOPAZ Test", "family": "topaz", "environment": "test", "enabled": True, "is_active": True}


def test_seed_preview_expands_category_and_stack_modes():
    preview = seed.preview_synthetic_category_seed(
        service=_Service(), category_id=42, price=5000, stack_mode="auto", copies_per_item=2, limit_items=10
    )
    assert preview["item_count"] == 3
    assert preview["listing_rows"] == 6
    assert preview["supply_units"] == (12 + 1 + 12) * 2
    assert preview["items"][0]["stack"] is True
    assert preview["items"][1]["stack"] is False

    stacks = seed.preview_synthetic_category_seed(
        service=_Service(), category_id=42, price=5000, stack_mode="stack", copies_per_item=1, limit_items=10
    )
    assert [row["item_id"] for row in stacks["items"]] == [100, 102]


def test_seed_bounds_are_fail_closed():
    with pytest.raises(seed.LegacyTestExecutionBlocked, match="copies_per_item"):
        seed.preview_synthetic_category_seed(
            service=_Service(), category_id=42, price=1, stack_mode="single", copies_per_item=6, limit_items=10
        )
    with pytest.raises(seed.LegacyTestExecutionBlocked, match="500"):
        seed.preview_synthetic_category_seed(
            service=_Service(), category_id=42, price=1, stack_mode="single", copies_per_item=5, limit_items=250
        )


def test_seed_execution_reuses_single_row_synthetic_executor(monkeypatch):
    calls = []
    monkeypatch.setattr(seed, "evaluate_legacy_test_write_gate", lambda **kw: SimpleNamespace(ready=True, issues=[]))
    monkeypatch.setattr(seed, "execute_legacy_test_synthetic_listing", lambda **kw: (
        calls.append(dict(kw)) or {"auction_id": 1000 + len(calls), "quantity": 12 if kw["stack"] else 1}
    ))
    result = seed.execute_synthetic_category_seed(
        service=_Service(), environment=_env(), seller_id=7, category_id=42, price=5000,
        stack_mode="auto", copies_per_item=1, limit_items=10, confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert result["status"] == "completed"
    assert result["committed"] == 3
    assert result["failed"] == 0
    assert result["listing_fee_charged"] == 0
    assert result["seller_inventory_removed"] == 0
    assert len(calls) == 3


def test_seed_execution_reports_partial_success(monkeypatch):
    monkeypatch.setattr(seed, "evaluate_legacy_test_write_gate", lambda **kw: SimpleNamespace(ready=True, issues=[]))
    def fake(**kw):
        if kw["item_id"] == 101:
            raise RuntimeError("synthetic failure")
        return {"auction_id": 9000 + kw["item_id"], "quantity": 1}
    monkeypatch.setattr(seed, "execute_legacy_test_synthetic_listing", fake)
    result = seed.execute_synthetic_category_seed(
        service=_Service(), environment=_env(), seller_id=7, category_id=42, price=5000,
        stack_mode="single", copies_per_item=1, limit_items=10, confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert result["status"] == "partial"
    assert result["committed"] == 2
    assert result["failed"] == 1
    assert any(row["item_id"] == 101 and row["status"] == "failed" for row in result["results"])


def test_seed_api_is_mounted_and_no_free_form_sql():
    api = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "synthetic_seed_api.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "integration.py").read_text(encoding="utf-8")
    assert '@router.post("/synthetic-category-preview.json")' in api
    assert '@router.post("/synthetic-category-seed.json")' in api
    assert "auction_house_synthetic_seed_router" in bridge
    assert 'payload.get("sql")' not in api
