from __future__ import annotations

from workbench.server_admin.auction_house.write_plans import (
    build_list_write_plan,
    build_purchase_write_plan,
    snapshot_fingerprint,
)


def _env(environment="test", name="Test", family="lsb"):
    return {
        "profile_id": 7,
        "name": name,
        "environment": environment,
        "family": family,
        "enabled": True,
        "is_active": True,
        "legacy": False,
    }


def _list_preview():
    return {
        "payload": {"item_id": 4096, "seller_id": 100, "price": 12000, "stack": False},
        "snapshot": {
            "item": {"item_id": 4096, "name": "test item", "stack_size": 12, "category_id": 9},
            "seller": {"char_id": 100, "char_name": "Seller"},
        },
        "economic_effect": {"listing_price": 12000, "quantity": 1, "price_per_item": 12000},
    }


def _purchase_preview(mode="admin_cleanup"):
    return {
        "payload": {"auction_id": 55, "buyer_id": 200 if mode == "normal_purchase" else None, "mode": mode},
        "snapshot": {
            "listing": {
                "auction_id": 55,
                "item_id": 4096,
                "seller_id": 100,
                "seller_name": "Seller",
                "asking_price": 12000,
                "stack": False,
                "listed_at": 123456,
            },
            "buyer": {"char_id": 200, "char_name": "Buyer"} if mode == "normal_purchase" else None,
        },
        "economic_effect": {"seller_compensation": 12000, "buyer_charge": 12000 if mode == "normal_purchase" else 0},
    }


def test_snapshot_fingerprint_is_deterministic_and_sensitive():
    left = snapshot_fingerprint({"b": 2, "a": 1})
    right = snapshot_fingerprint({"a": 1, "b": 2})
    changed = snapshot_fingerprint({"a": 1, "b": 3})
    assert left == right
    assert left != changed
    assert len(left) == 64


def test_lsb_listing_plan_requires_trigger_and_never_becomes_executable():
    plan = build_list_write_plan(
        adapter_family="lsb-compatible",
        environment=_env(),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers={"auction_house_list"},
    )
    assert plan.required_triggers == ("auction_house_list",)
    assert not any(issue.code.startswith("lineage_") for issue in plan.issues)
    assert plan.executor_enabled is False
    assert plan.executable is False
    assert any(issue.code == "executor_not_enabled" for issue in plan.issues)
    assert plan.audit.operation == "auction_house.list_item"


def test_lsb_purchase_plan_requires_auction_and_delivery_triggers():
    plan = build_purchase_write_plan(
        adapter_family="lsb-compatible",
        environment=_env(),
        preview=_purchase_preview("normal_purchase"),
        schema_tables={"auction_house", "chars", "delivery_box"},
        schema_triggers={"auction_house_buy"},
    )
    assert set(plan.required_triggers) == {"auction_house_buy", "delivery_box_insert"}
    assert any(issue.code == "missing_trigger" and "delivery_box_insert" in issue.message for issue in plan.issues)
    assert plan.executable is False


def test_live_environment_requires_exact_profile_name_confirmation():
    plan = build_list_write_plan(
        adapter_family="lsb-compatible",
        environment=_env("live", "Production"),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers={"auction_house_list"},
        live_confirmation="production",
    )
    assert any(issue.code == "live_confirmation_required" for issue in plan.issues)

    confirmed = build_list_write_plan(
        adapter_family="lsb-compatible",
        environment=_env("live", "Production"),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers={"auction_house_list"},
        live_confirmation="Production",
    )
    assert not any(issue.code == "live_confirmation_required" for issue in confirmed.issues)
    assert confirmed.executable is False


def test_legacy_fallback_environment_is_never_write_ready():
    identity = _env("legacy", "DSP", family="dsp")
    identity["legacy"] = True
    plan = build_purchase_write_plan(
        adapter_family="legacy-dsp-topaz-compatible",
        environment=identity,
        preview=_purchase_preview(),
        schema_tables={"auction_house", "chars", "delivery_box"},
        schema_triggers={"auction_house_buy", "delivery_box_insert"},
    )
    assert any(issue.code == "legacy_environment_unclassified" for issue in plan.issues)
    assert any(issue.code == "lineage_execution_contract_incomplete" for issue in plan.issues)
    assert plan.contract_ready is False
    assert plan.executable is False


def test_named_dsp_topaz_environment_reports_execution_contract_incomplete():
    for family in ("topaz", "dsp"):
        identity = _env("test", f"{family} Test", family=family)
        plan = build_list_write_plan(
            adapter_family="legacy-dsp-topaz-compatible",
            environment=identity,
            preview=_list_preview(),
            schema_tables={"auction_house", "item_basic", "chars"},
            schema_triggers={"auction_house_buy", "delivery_box_insert"},
        )
        issue = next(issue for issue in plan.issues if issue.code == "lineage_execution_contract_incomplete")
        assert family.capitalize() in issue.message or family.upper() in issue.message
        assert not any(issue.code == "lineage_semantics_unverified" for issue in plan.issues)
        assert plan.contract_ready is False
        assert plan.executor_enabled is False
        assert plan.executable is False


def test_profile_schema_mismatch_and_auto_profile_fail_closed():
    mismatch = build_list_write_plan(
        adapter_family="legacy-dsp-topaz-compatible",
        environment=_env(family="lsb"),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers=set(),
    )
    assert any(issue.code == "lineage_schema_mismatch" for issue in mismatch.issues)

    auto = build_list_write_plan(
        adapter_family="lsb-compatible",
        environment=_env(family="auto"),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers={"auction_house_list"},
    )
    assert any(issue.code == "lineage_not_explicit" for issue in auto.issues)
    assert auto.executable is False


def test_normal_purchase_requires_exact_buyer_snapshot():
    preview = _purchase_preview("normal_purchase")
    preview["snapshot"]["buyer"] = None
    plan = build_purchase_write_plan(
        adapter_family="lsb-compatible",
        environment=_env(),
        preview=preview,
        schema_tables={"auction_house", "chars", "delivery_box"},
        schema_triggers={"auction_house_buy", "delivery_box_insert"},
    )
    assert any(issue.code == "buyer_snapshot_missing" for issue in plan.issues)
    assert plan.executable is False


def test_write_plan_contains_no_executable_sql_or_apply_function():
    plan = build_list_write_plan(
        adapter_family="lsb-compatible",
        environment=_env(),
        preview=_list_preview(),
        schema_tables={"auction_house", "item_basic", "chars"},
        schema_triggers={"auction_house_list"},
    )
    rendered = repr(plan.as_dict()).upper()
    assert "INSERT INTO" not in rendered
    assert "UPDATE AUCTION_HOUSE" not in rendered
    assert "DELETE FROM" not in rendered
    assert plan.executable is False
