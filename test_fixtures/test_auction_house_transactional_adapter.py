from __future__ import annotations

from workbench.server_admin.auction_house.transactional_adapter import (
    prepare_legacy_transaction,
    simulate_transaction_rollback,
)


def _env(family: str):
    return {
        "profile_id": 17,
        "name": f"{family.upper()} Test",
        "environment": "test",
        "family": family,
        "enabled": True,
        "is_active": True,
    }


def _purchase_preview():
    return {
        "payload": {"auction_id": 55, "buyer_id": 200, "mode": "normal_purchase"},
        "snapshot": {
            "listing": {
                "auction_id": 55,
                "item_id": 4096,
                "stack": False,
                "seller_id": 100,
                "asking_price": 12000,
                "listed_at": 123456,
            },
            "buyer": {"char_id": 200, "char_name": "Buyer"},
        },
    }


def _listing_preview():
    return {
        "payload": {"item_id": 4096, "seller_id": 100, "price": 12000, "stack": False},
        "snapshot": {
            "item": {"item_id": 4096, "name": "test item", "stack_size": 12, "category_id": 9},
            "seller": {"char_id": 100, "char_name": "Seller"},
            "inventory": {"item_id": 4096, "quantity": 3, "slot": 4},
            "active_listing_count": 2,
            "seller_gil": 50000,
        },
    }


def test_dsp_and_topaz_fixtures_validate_but_never_become_executable():
    for family in ("dsp", "topaz"):
        preview = _purchase_preview()
        prepared = prepare_legacy_transaction(
            family=family,
            schema_family_hint="legacy-dsp-topaz-compatible",
            operation="purchase_item",
            environment=_env(family),
            preview=preview,
            current={
                "snapshot": preview["snapshot"],
                "claim_count": 1,
                "cheapest_qualifying_auction_id": 55,
            },
            preview_environment=_env(family),
        )
        assert prepared.validation_ready is True
        assert prepared.executor_enabled is False
        assert prepared.executable is False
        assert prepared.preview_fingerprint == prepared.current_fingerprint


def test_stale_purchase_preview_is_rejected():
    preview = _purchase_preview()
    current = {"snapshot": {**preview["snapshot"], "listing": {**preview["snapshot"]["listing"], "asking_price": 13000}}}
    prepared = prepare_legacy_transaction(
        family="topaz",
        schema_family_hint="legacy-dsp-topaz-compatible",
        operation="purchase_item",
        environment=_env("topaz"),
        preview=preview,
        current=current,
    )
    assert any(issue.code == "stale_preview" for issue in prepared.issues)
    assert prepared.validation_ready is False
    assert prepared.executable is False


def test_purchase_rejects_changed_cheapest_row_and_bad_claim_cardinality():
    preview = _purchase_preview()
    prepared = prepare_legacy_transaction(
        family="dsp",
        schema_family_hint="legacy-dsp-topaz-compatible",
        operation="purchase_item",
        environment=_env("dsp"),
        preview=preview,
        current={
            "snapshot": preview["snapshot"],
            "claim_count": 2,
            "cheapest_qualifying_auction_id": 54,
        },
    )
    codes = {issue.code for issue in prepared.issues}
    assert "claim_cardinality_invalid" in codes
    assert "cheapest_listing_changed" in codes
    assert prepared.validation_ready is False


def test_preview_cannot_cross_environment_or_lineage():
    preview = _listing_preview()
    old_env = _env("topaz")
    old_env["profile_id"] = 1
    prepared = prepare_legacy_transaction(
        family="topaz",
        schema_family_hint="legacy-dsp-topaz-compatible",
        operation="list_item",
        environment=_env("topaz"),
        preview=preview,
        current={"snapshot": preview["snapshot"]},
        preview_environment=old_env,
    )
    assert any(issue.code == "preview_environment_mismatch" for issue in prepared.issues)

    mismatch = prepare_legacy_transaction(
        family="dsp",
        schema_family_hint="legacy-dsp-topaz-compatible",
        operation="list_item",
        environment=_env("topaz"),
        preview=preview,
        current={"snapshot": preview["snapshot"]},
    )
    assert any(issue.code == "environment_lineage_mismatch" for issue in mismatch.issues)


def test_schema_mismatch_fails_closed():
    preview = _listing_preview()
    prepared = prepare_legacy_transaction(
        family="dsp",
        schema_family_hint="lsb-compatible",
        operation="list_item",
        environment=_env("dsp"),
        preview=preview,
        current={"snapshot": preview["snapshot"]},
    )
    assert any(issue.code == "execution_contract_schema_mismatch" for issue in prepared.issues)
    assert prepared.validation_ready is False


def test_rollback_harness_restores_exact_fixture_state_on_each_failure_stage():
    original = {
        "auction": {"auction_id": 55, "sold": False},
        "inventory": {"buyer_item_count": 0},
        "gil": {"buyer": 50000},
        "delivery": {"seller_rows": 0},
    }
    staged = {
        "auction": {"auction_id": 55, "sold": True},
        "inventory": {"buyer_item_count": 1},
        "gil": {"buyer": 38000},
        "delivery": {"seller_rows": 1},
    }
    for stage in staged:
        result = simulate_transaction_rollback(original, staged_changes=staged, fail_after_stage=stage)
        assert result.rolled_back is True
        assert result.failure_stage == stage
        assert result.after == original
        assert original["auction"]["sold"] is False


def test_successful_fixture_simulation_changes_only_working_copy():
    original = {"auction": {"sold": False}, "gil": {"buyer": 50000}}
    result = simulate_transaction_rollback(
        original,
        staged_changes={"auction": {"sold": True}, "gil": {"buyer": 38000}},
    )
    assert result.rolled_back is False
    assert result.after["auction"]["sold"] is True
    assert original == {"auction": {"sold": False}, "gil": {"buyer": 50000}}


def test_foundation_contains_no_execution_escape_hatch():
    preview = _purchase_preview()
    prepared = prepare_legacy_transaction(
        family="dsp",
        schema_family_hint="legacy-dsp-topaz-compatible",
        operation="purchase_item",
        environment=_env("dsp"),
        preview=preview,
        current={"snapshot": preview["snapshot"], "claim_count": 1, "cheapest_qualifying_auction_id": 55},
    )
    rendered = repr(prepared.as_dict()).upper()
    assert "INSERT INTO" not in rendered
    assert "UPDATE AUCTION_HOUSE" not in rendered
    assert "DELETE FROM" not in rendered
    assert prepared.executable is False
