from __future__ import annotations

from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import rule_cleanup as rc


class _Service:
    schema = SimpleNamespace(family_hint="legacy-dsp-topaz-compatible")


def _env():
    return {"name": "TOPAZ Test", "family": "topaz", "environment": "test", "enabled": True, "is_active": True}


def _rows():
    return [
        {"auction_id": 10, "item_id": 100, "item_name": "Potion", "category_id": 42, "seller_id": 7, "seller_name": "Seller", "listed_at": 1000, "asking_price": 5000},
        {"auction_id": 11, "item_id": 101, "item_name": "Ether", "category_id": 42, "seller_id": 7, "seller_name": "Seller", "listed_at": 2000, "asking_price": 9000},
    ]


def test_criteria_resolves_age_to_listed_before_and_bounds_limit():
    criteria = rc.criteria_from_payload({"min_age_days": 30, "limit": 999, "min_price": 100, "max_price": 1000}, now=4_000_000)
    assert criteria.listed_before == 4_000_000 - 30 * 86400
    assert criteria.limit == 100
    assert criteria.min_price == 100
    assert criteria.max_price == 1000


def test_criteria_rejects_inverted_price_range():
    with pytest.raises(rc.LegacyTestExecutionBlocked, match="min_price"):
        rc.criteria_from_payload({"min_price": 200, "max_price": 100})


def test_preview_binds_exact_target_set(monkeypatch):
    monkeypatch.setattr(rc, "_select", lambda service, criteria: _rows())
    criteria = rc.CleanupCriteria(seller_id=7, category_id=42, listed_before=3000, limit=100)
    preview = rc.preview_cleanup(_Service(), criteria, now=4_000_000)
    assert preview["count"] == 2
    assert preview["aggregate_asking_value"] == 14000
    assert preview["targets"][0]["auction_id"] == 10
    assert len(preview["preview_token"]) == 64


def test_preview_token_changes_when_price_or_target_changes(monkeypatch):
    criteria = rc.CleanupCriteria(seller_id=7)
    rows = _rows()
    monkeypatch.setattr(rc, "_select", lambda service, c: rows)
    first = rc.preview_cleanup(_Service(), criteria)["preview_token"]
    rows[0] = dict(rows[0], asking_price=5001)
    second = rc.preview_cleanup(_Service(), criteria)["preview_token"]
    assert first != second


def test_execute_reuses_batch_executor_and_exact_preview(monkeypatch):
    rows = _rows()
    monkeypatch.setattr(rc, "_select", lambda service, criteria: rows)
    criteria = rc.CleanupCriteria(seller_id=7, limit=100)
    token = rc.preview_cleanup(_Service(), criteria)["preview_token"]
    called = {}

    def fake_batch(**kwargs):
        called.update(kwargs)
        return {"status": "completed", "committed": 2, "failed": 0}

    monkeypatch.setattr(rc, "execute_legacy_test_batch", fake_batch)
    result = rc.execute_cleanup(
        service=_Service(), environment=_env(), criteria=criteria, preview_token=token,
        action="admin_buy", confirmation="TOPAZ Test", feature_enabled=True,
    )
    assert result["status"] == "completed"
    assert [t["auction_id"] for t in called["targets"]] == [10, 11]
    assert [t["expected_price"] for t in called["targets"]] == [5000, 9000]
    assert called["action"] == "admin_buy"


def test_execute_rejects_stale_preview_before_any_batch_action(monkeypatch):
    rows = _rows()
    monkeypatch.setattr(rc, "_select", lambda service, criteria: rows)
    criteria = rc.CleanupCriteria(seller_id=7)
    token = rc.preview_cleanup(_Service(), criteria)["preview_token"]
    rows.pop()
    monkeypatch.setattr(rc, "execute_legacy_test_batch", lambda **kwargs: pytest.fail("batch must not execute"))
    with pytest.raises(rc.LegacyTestExecutionBlocked, match="stale"):
        rc.execute_cleanup(
            service=_Service(), environment=_env(), criteria=criteria, preview_token=token,
            action="return_to_seller", confirmation="TOPAZ Test", feature_enabled=True,
        )


def test_execute_rejects_bad_test_confirmation(monkeypatch):
    monkeypatch.setattr(rc, "_select", lambda service, criteria: _rows())
    criteria = rc.CleanupCriteria()
    token = rc.preview_cleanup(_Service(), criteria)["preview_token"]
    with pytest.raises(rc.LegacyTestExecutionBlocked, match="test_confirmation_required"):
        rc.execute_cleanup(
            service=_Service(), environment=_env(), criteria=criteria, preview_token=token,
            action="admin_buy", confirmation="wrong", feature_enabled=True,
        )


def test_cleanup_ui_and_routes_are_mounted():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    integration = (root / "src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    api = (root / "src/workbench/server_admin/auction_house/cleanup_api.py").read_text(encoding="utf-8")
    template = (root / "gui/templates/auction_house_cleanup.html").read_text(encoding="utf-8")
    script = (root / "gui/static/auction_house_cleanup.js").read_text(encoding="utf-8")
    console_template = (root / "gui/templates/auction_house_console.html").read_text(encoding="utf-8")
    console_script = (root / "gui/static/auction_house_console.js").read_text(encoding="utf-8")
    assert "auction_house_cleanup_router" in integration
    assert 'data-t="cleanup"' in console_template
    assert "/auction-house/cleanup/preview.json" in console_script
    assert '"/auction-house/cleanup/preview.json"' in api
    assert '"/auction-house/test-write/cleanup.json"' in api
    assert "Preview exact targets" in template
    assert "30-day stale" in template
    assert "preview_token" in script
    assert "Admin Buy previewed" in template
    assert "Return previewed" in template
