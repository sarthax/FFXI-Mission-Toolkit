from workbench.server_admin.auction_house.execution_contracts import (
    evaluate_execution_contract,
    execution_contract_for_family,
)


def test_topaz_contract_is_fully_specified_but_non_executable():
    contract = execution_contract_for_family("topaz")
    assert contract is not None
    assert contract.status == "specified_non_executable"
    assert contract.executor_permitted is False
    assert contract.schema_shape == "legacy-dsp-topaz-compatible"
    assert "auction_house_buy" in contract.required_triggers
    assert "delivery_box_insert" in contract.required_triggers
    assert any("cheapest qualifying" in step for step in contract.purchase_sequence)
    assert any("full stack" in step for step in contract.inventory_guards)
    assert any("direct chars.gil edit" in step for step in contract.settlement_guards)
    assert any("roll back" in step for step in contract.rollback_guards)
    assert any("fingerprint" in step for step in contract.stale_preview_guards)


def test_dsp_contract_has_same_required_safety_classes_but_explicit_family():
    contract = execution_contract_for_family("dsp")
    assert contract is not None
    assert contract.family == "dsp"
    assert contract.executor_permitted is False
    assert contract.concurrency_guards
    assert contract.stale_preview_guards
    assert contract.inventory_guards
    assert contract.settlement_guards
    assert contract.rollback_guards
    assert contract.audit_guards
    assert contract.remaining_gates


def test_matching_legacy_profile_reports_specified_but_still_blocked():
    result = evaluate_execution_contract(
        profile_family="topaz",
        schema_family_hint="legacy-dsp-topaz-compatible",
    )
    assert result["contract_specified"] is True
    assert result["executor_permitted"] is False
    assert any(issue["code"] == "execution_adapter_not_implemented" for issue in result["issues"])


def test_schema_mismatch_fails_closed():
    result = evaluate_execution_contract(
        profile_family="dsp",
        schema_family_hint="lsb-compatible",
    )
    assert result["contract_specified"] is False
    assert result["executor_permitted"] is False
    assert any(issue["code"] == "execution_contract_schema_mismatch" for issue in result["issues"])


def test_unknown_and_lsb_profiles_do_not_reuse_legacy_contract():
    for family in ("auto", "unknown", "lsb", None):
        result = evaluate_execution_contract(
            profile_family=family,
            schema_family_hint="legacy-dsp-topaz-compatible",
        )
        assert result["contract_specified"] is False
        assert result["executor_permitted"] is False
        assert result["contract"] is None


def test_contract_contains_no_executable_sql_or_executor_hook():
    for family in ("topaz", "dsp"):
        contract = execution_contract_for_family(family)
        rendered = repr(contract.as_dict()).upper()
        assert "INSERT INTO" not in rendered
        assert "UPDATE AUCTION_HOUSE" not in rendered
        assert "DELETE FROM" not in rendered
        assert "EXECUTE(" not in rendered
        assert contract.executor_permitted is False
