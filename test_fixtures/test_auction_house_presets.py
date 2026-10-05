from pathlib import Path

import pytest

from workbench.server_admin.auction_house.preset_api import _preset_preview_token
from workbench.server_admin.auction_house.presets import (
    PresetError,
    delete_preset,
    get_preset,
    list_presets,
    normalize_preset_config,
    save_preset,
)


def test_cleanup_preset_round_trip(tmp_path: Path):
    db = tmp_path / "presets.db"
    row = save_preset(
        name="90-day stale return",
        kind="cleanup",
        config={"min_age_days": 90, "limit": 250, "default_action": "return_to_seller"},
        path=db,
    )
    assert row["kind"] == "cleanup"
    assert row["config"]["min_age_days"] == 90.0
    assert row["config"]["limit"] == 100
    assert row["config"]["default_action"] == "return_to_seller"
    assert get_preset(row["preset_id"], path=db)["name"] == "90-day stale return"
    assert [item["preset_id"] for item in list_presets(path=db)] == [row["preset_id"]]
    assert delete_preset(row["preset_id"], path=db) is True
    assert list_presets(path=db) == []


def test_synthetic_seed_preset_normalizes_bounds(tmp_path: Path):
    db = tmp_path / "presets.db"
    row = save_preset(
        name="Weapons supply",
        kind="synthetic_seed",
        config={
            "seller_id": 10,
            "category_id": 3,
            "price": 5000,
            "stack_mode": "AUTO",
            "copies_per_item": 99,
            "limit_items": 999,
        },
        path=db,
    )
    assert row["config"] == {
        "seller_id": 10,
        "category_id": 3,
        "price": 5000,
        "stack_mode": "auto",
        "copies_per_item": 5,
        "limit_items": 250,
    }


def test_preset_rejects_execution_authorization_fields():
    with pytest.raises(PresetError, match="Unsupported preset field"):
        normalize_preset_config("cleanup", {"min_age_days": 30, "confirmation": "Test"})
    with pytest.raises(PresetError, match="Unsupported preset field"):
        normalize_preset_config("synthetic_seed", {"seller_id": 1, "category_id": 2, "price": 3, "preview_token": "abc"})


def test_cleanup_preset_rejects_invalid_action_and_price_range():
    with pytest.raises(PresetError, match="default_action"):
        normalize_preset_config("cleanup", {"default_action": "delete"})
    with pytest.raises(PresetError, match="min_price"):
        normalize_preset_config("cleanup", {"min_price": 200, "max_price": 100})


def test_preset_update_preserves_identity_and_creation_time(tmp_path: Path):
    db = tmp_path / "presets.db"
    first = save_preset(name="Old", kind="cleanup", config={"min_age_days": 30}, path=db)
    updated = save_preset(
        preset_id=first["preset_id"],
        name="New",
        kind="cleanup",
        config={"min_age_days": 60},
        path=db,
    )
    assert updated["preset_id"] == first["preset_id"]
    assert updated["created_at_utc"] == first["created_at_utc"]
    assert updated["name"] == "New"
    assert updated["config"]["min_age_days"] == 60.0


def test_cleanup_preview_token_ignores_generated_timestamp_but_binds_targets():
    preset = {
        "preset_id": "p1",
        "updated_at_utc": "2026-10-05T00:00:00Z",
        "kind": "cleanup",
        "config": {"min_age_days": 90},
    }
    preview = {
        "criteria": {"listed_before": 123, "limit": 100},
        "preview_token": "exact-live-targets",
        "generated_at": 1000,
    }
    token1 = _preset_preview_token(preset, preview)
    token2 = _preset_preview_token(preset, {**preview, "generated_at": 2000})
    token3 = _preset_preview_token(preset, {**preview, "preview_token": "changed-targets"})
    assert token1 == token2
    assert token1 != token3


def test_seed_preview_token_binds_expanded_item_set():
    preset = {
        "preset_id": "p2",
        "updated_at_utc": "2026-10-05T00:00:00Z",
        "kind": "synthetic_seed",
        "config": {"seller_id": 1, "category_id": 2, "price": 100, "stack_mode": "auto"},
    }
    preview = {
        "category_id": 2,
        "price": 100,
        "stack_mode": "auto",
        "copies_per_item": 1,
        "limit_items": 100,
        "items": [{"item_id": 10, "stack": False, "copies": 1, "price": 100}],
    }
    token1 = _preset_preview_token(preset, preview)
    changed = {**preview, "items": [{"item_id": 11, "stack": False, "copies": 1, "price": 100}]}
    assert token1 != _preset_preview_token(preset, changed)


def test_preset_ui_and_api_are_mounted():
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    template = Path("gui/templates/auction_house_presets.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_presets.js").read_text(encoding="utf-8")
    api = Path("src/workbench/server_admin/auction_house/preset_api.py").read_text(encoding="utf-8")
    assert "auction_house_preset_api_router" in integration
    assert "auction_house_preset_ui_router" in integration
    assert '"AH Presets"' in integration
    assert "/auction-house/presets" in integration
    assert "/auction-house/presets/preview.json" in script
    assert "/auction-house/presets/execute.json" in script
    assert "preset_preview_token" in api
    assert "Saved preset preview is stale" in api
    assert "Presets never store execution confirmation" in template
