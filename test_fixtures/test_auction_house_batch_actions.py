from __future__ import annotations

from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import batch_actions as ba
from workbench.server_admin.auction_house import safe_return as sr


class _Service:
    schema = SimpleNamespace(family_hint="legacy-dsp-topaz-compatible")


def _env():
    return {"name": "TOPAZ Test", "family": "topaz", "environment": "test", "enabled": True, "is_active": True}


def test_batch_admin_buy_reuses_single_row_executor_and_reports_partial(monkeypatch):
    calls = []
    def fake_admin_buy(**kwargs):
        calls.append(kwargs["auction_id"])
        if kwargs["auction_id"] == 2:
            raise RuntimeError("stale row")
        return {"status": "committed", "auction_id": kwargs["auction_id"]}
    monkeypatch.setattr(ba, "execute_legacy_test_admin_buy", fake_admin_buy)

    result = ba.execute_legacy_test_batch(
        service=_Service(), environment=_env(), action="admin_buy",
        targets=[{"auction_id": 1, "expected_price": 100}, {"auction_id": 2, "expected_price": 200}],
        confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert calls == [1, 2]
    assert result["status"] == "partial"
    assert result["committed"] == 1
    assert result["failed"] == 1
    assert result["partial_success_possible"] is True


def test_batch_return_reuses_safe_return(monkeypatch):
    calls = []
    monkeypatch.setattr(ba, "execute_legacy_test_safe_return", lambda **kw: calls.append(kw["auction_id"]) or {"status": "committed"})
    result = ba.execute_legacy_test_batch(
        service=_Service(), environment=_env(), action="return_to_seller",
        targets=[{"auction_id": 4}, {"auction_id": 5}], confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert calls == [4, 5]
    assert result["status"] == "completed"
    assert result["committed"] == 2


def test_batch_rejects_bad_gate_duplicates_and_oversize():
    with pytest.raises(ba.LegacyTestExecutionBlocked, match="test_confirmation_required"):
        ba.execute_legacy_test_batch(
            service=_Service(), environment=_env(), action="return_to_seller",
            targets=[{"auction_id": 1}], confirmation="wrong", feature_enabled=True,
        )
    with pytest.raises(ba.LegacyTestExecutionBlocked, match="Duplicate"):
        ba.execute_legacy_test_batch(
            service=_Service(), environment=_env(), action="return_to_seller",
            targets=[{"auction_id": 1}, {"auction_id": 1}], confirmation="TOPAZ Test", feature_enabled=True,
        )
    with pytest.raises(ba.LegacyTestExecutionBlocked, match="limited to 100"):
        ba.execute_legacy_test_batch(
            service=_Service(), environment=_env(), action="return_to_seller",
            targets=[{"auction_id": i + 1} for i in range(101)], confirmation="TOPAZ Test", feature_enabled=True,
        )


def test_safe_return_prefers_transactional_inventory(monkeypatch):
    monkeypatch.setattr(sr, "_table_engines", lambda connection, names: {
        "auction_house": "InnoDB", "char_inventory": "InnoDB", "delivery_box": "InnoDB"
    })
    monkeypatch.setattr(sr, "execute_legacy_test_return_to_seller", lambda **kw: {"status": "committed"})
    service = SimpleNamespace(connection=object())
    result = sr.execute_legacy_test_safe_return(
        service=service, environment=_env(), auction_id=1, confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert result["return_method"] == "inventory"


def test_safe_return_falls_back_to_delivery_for_myisam_inventory(monkeypatch):
    monkeypatch.setattr(sr, "_table_engines", lambda connection, names: {
        "auction_house": "InnoDB", "char_inventory": "MyISAM", "delivery_box": "InnoDB"
    })
    monkeypatch.setattr(sr, "execute_legacy_test_delivery_return", lambda **kw: {"status": "committed", "return_method": "delivery_box"})
    service = SimpleNamespace(connection=object())
    result = sr.execute_legacy_test_safe_return(
        service=service, environment=_env(), auction_id=1, confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert result["return_method"] == "delivery_box"


def test_safe_return_blocks_when_no_transactional_strategy(monkeypatch):
    monkeypatch.setattr(sr, "_table_engines", lambda connection, names: {
        "auction_house": "InnoDB", "char_inventory": "MyISAM", "delivery_box": "MyISAM"
    })
    with pytest.raises(sr.LegacyTestExecutionBlocked, match="No rollback-safe return path"):
        sr.execute_legacy_test_safe_return(
            service=SimpleNamespace(connection=object()), environment=_env(), auction_id=1,
            confirmation="TOPAZ Test", feature_enabled=True,
        )
