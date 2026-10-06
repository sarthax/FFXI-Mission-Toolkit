import pytest

from workbench.server_admin.auction_house import presets as P
from workbench.server_admin.auction_house.restock_presets import (
    BUILTIN_CLEANUP_PRESETS, BUILTIN_RESTOCK_PRESETS, MAX_ITEMS, normalize_restock_config)


def test_restock_config_needs_a_filter_and_caps_items():
    with pytest.raises(P.PresetError):
        normalize_restock_config({"target": 3})
    cfg = normalize_restock_config({"category_ids": [35], "max_items": 500, "target": 200})
    assert cfg["max_items"] == MAX_ITEMS and cfg["target"] == 99 and cfg["price_source"] == "market"


def test_restock_config_validation():
    with pytest.raises(P.PresetError):
        normalize_restock_config({"min_level": 20, "max_level": 10})
    with pytest.raises(P.PresetError):
        normalize_restock_config({"category_ids": [1], "price_source": "fixed"})


def test_every_builtin_preset_is_valid():
    for p in BUILTIN_RESTOCK_PRESETS + BUILTIN_CLEANUP_PRESETS:
        P.normalize_preset_config(p["kind"], p["config"])


def test_seed_is_idempotent_and_default_seller_rules(tmp_path):
    db = tmp_path / "p.db"
    n = P.seed_builtin_presets(path=db)
    assert n == len(BUILTIN_RESTOCK_PRESETS) + len(BUILTIN_CLEANUP_PRESETS)
    assert P.seed_builtin_presets(path=db) == 0
    assert P.get_default_seller(path=db)["char_name"] == "AHRestock"
    assert P.set_default_seller(990101, "Shopkeep", path=db)["char_id"] == 990101
    with pytest.raises(P.PresetError):
        P.set_default_seller(21828, "Real", path=db)
    with pytest.raises(P.PresetError):
        P.set_default_seller(990101, "bad name!", path=db)


def test_restock_item_lists_normalize_and_count_as_scope():
    cfg = normalize_restock_config({"item_ids": [5, "5", 3, -1], "exclude_item_ids": [9]})
    assert cfg["item_ids"] == [3, 5] and cfg["exclude_item_ids"] == [9]
    with pytest.raises(P.PresetError):
        normalize_restock_config({"exclude_item_ids": [9]})
    assert P.normalize_preset_config("restock", {"category_ids": [1], "exclude_item_ids": [9]})["exclude_item_ids"] == [9]


def test_vendor_ratio_is_a_cleanup_field_and_builtin_presets_ship():
    cfg = P.normalize_preset_config("cleanup", {"max_vendor_ratio": 1.0, "default_action": "admin_buy"})
    assert cfg["max_vendor_ratio"] == 1.0
    from workbench.server_admin.auction_house.rule_cleanup import criteria_from_payload
    assert criteria_from_payload({"max_vendor_ratio": "0.5"}).max_vendor_ratio == 0.5
    with pytest.raises(Exception):
        criteria_from_payload({"max_vendor_ratio": 0})
    names = {p["name"] for p in BUILTIN_CLEANUP_PRESETS}
    assert {"Below vendor value: admin buy", "Below vendor value: return"} <= names


def test_seed_upgrade_only_adds_new_builtins(tmp_path):
    db = tmp_path / "p.db"
    P.seed_builtin_presets(path=db)
    P.set_meta("builtin_presets_version", "1", path=db)
    gone = [r for r in P.list_presets(path=db) if r["name"].startswith("Below vendor")]
    for r in gone:
        P.delete_preset(r["preset_id"], path=db)
    old = next(r for r in P.list_presets(path=db) if r["name"] == "Stale 30 days: return")
    P.delete_preset(old["preset_id"], path=db)
    assert P.seed_builtin_presets(path=db) == 2
    names = {r["name"] for r in P.list_presets(path=db)}
    assert "Stale 30 days: return" not in names and "Below vendor value: return" in names
