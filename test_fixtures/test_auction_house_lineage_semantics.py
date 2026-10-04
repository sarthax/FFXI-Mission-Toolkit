from workbench.server_admin.auction_house.lineage_semantics import (
    evaluate_lineage_semantics,
    semantics_for_family,
)


def test_lsb_semantics_are_source_verified():
    contract = semantics_for_family("lsb")
    assert contract.verification == "verified"
    assert contract.writes_allowed_by_semantics is True
    assert contract.schema_shape == "lsb-compatible"
    assert "auction_house_buy" in contract.required_triggers
    assert "delivery_box_insert" in contract.required_triggers
    assert "direct chars.gil edit" in contract.seller_settlement


def test_lsb_requires_explicit_matching_profile_family():
    good = evaluate_lineage_semantics(profile_family="lsb", schema_family_hint="lsb-compatible")
    assert good["source_semantics_verified"] is True
    assert good["semantics_verified"] is True
    assert good["writes_allowed_by_semantics"] is True

    auto = evaluate_lineage_semantics(profile_family="auto", schema_family_hint="lsb-compatible")
    assert auto["writes_allowed_by_semantics"] is False
    assert any(issue["code"] == "lineage_not_explicit" for issue in auto["issues"])


def test_family_schema_mismatch_fails_closed():
    result = evaluate_lineage_semantics(
        profile_family="lsb",
        schema_family_hint="legacy-dsp-topaz-compatible",
    )
    assert result["writes_allowed_by_semantics"] is False
    assert any(issue["code"] == "lineage_schema_mismatch" for issue in result["issues"])


def test_topaz_source_semantics_are_verified_but_execution_stays_blocked():
    contract = semantics_for_family("topaz")
    assert contract.verification == "source_verified_preview_only"
    assert contract.schema_shape == "legacy-dsp-topaz-compatible"
    assert contract.writes_allowed_by_semantics is False
    assert "auction_house_buy" in contract.required_triggers
    assert any(e.path == "src/map/packet_system.cpp" for e in contract.source_evidence)

    result = evaluate_lineage_semantics(
        profile_family="topaz",
        schema_family_hint="legacy-dsp-topaz-compatible",
    )
    assert result["source_semantics_verified"] is True
    assert result["semantics_verified"] is False
    assert result["writes_allowed_by_semantics"] is False
    assert any(issue["code"] == "lineage_execution_contract_incomplete" for issue in result["issues"])


def test_dsp_source_semantics_are_verified_but_execution_stays_blocked():
    contract = semantics_for_family("dsp")
    assert contract.verification == "source_verified_preview_only"
    assert contract.schema_shape == "legacy-dsp-topaz-compatible"
    assert contract.writes_allowed_by_semantics is False
    assert "delivery_box_insert" in contract.required_triggers
    assert any(e.path == "src/map/packet_system.cpp" for e in contract.source_evidence)

    result = evaluate_lineage_semantics(
        profile_family="dsp",
        schema_family_hint="legacy-dsp-topaz-compatible",
    )
    assert result["source_semantics_verified"] is True
    assert result["semantics_verified"] is False
    assert result["writes_allowed_by_semantics"] is False
    assert any(issue["code"] == "lineage_execution_contract_incomplete" for issue in result["issues"])


def test_shared_legacy_shape_cannot_choose_topaz_or_dsp():
    auto = evaluate_lineage_semantics(
        profile_family="auto",
        schema_family_hint="legacy-dsp-topaz-compatible",
    )
    assert auto["writes_allowed_by_semantics"] is False
    assert auto["contract"]["family"] == "unknown"


def test_unknown_family_is_unverified():
    contract = semantics_for_family("mystery")
    assert contract.verification == "unverified"
    assert contract.writes_allowed_by_semantics is False
