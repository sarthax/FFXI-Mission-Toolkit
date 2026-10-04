from types import SimpleNamespace

from src.workbench.server_admin.auction_house.validation_report import build_validation_report


class Obj(SimpleNamespace):
    def as_dict(self):
        return dict(self.__dict__)


def _environment():
    return {"profile_id": "legacy-test", "name": "Legacy Test", "environment": "TEST", "family": "topaz", "is_active": True}


def _readiness():
    return {
        "database": "topaz",
        "legacy_listing_shape_present": True,
        "legacy_purchase_prerequisites_present": True,
        "lsb_listing_ready": False,
        "lsb_purchase_ready": False,
        "tables": ("auction_house", "item_basic", "chars", "delivery_box"),
        "triggers": ("auction_house_buy", "delivery_box_insert"),
    }


def _healthy():
    return dict(
        environment=_environment(),
        schema_family_hint="legacy-dsp-topaz-compatible",
        readiness=_readiness(),
        prepared=Obj(operation="list_item", validation_ready=True, issues=[]),
        evidence=Obj(transaction_mode="read_only_rolled_back"),
        invariants=Obj(invariants_ready=True, issues=[]),
        policy_load=Obj(policy_ready=True, issues=[]),
        policy_binding=Obj(binding_ready=True, issues=[]),
    )


def test_healthy_legacy_evidence_is_read_only_ready_but_never_execution_ready():
    report = build_validation_report(**_healthy())
    assert report["status"] == "ready"
    assert report["read_only_validation_ready"] is True
    assert report["execution_ready"] is False
    assert report["executor_enabled"] is False
    assert report["write_enabled"] is False
    # DSP/Topaz source semantics deliberately remain an execution blocker.
    assert "lineage_execution_contract_incomplete" in {item["code"] for item in report["blockers"]}


def test_stale_database_snapshot_blocks_report():
    values = _healthy()
    values["prepared"] = Obj(
        operation="list_item",
        validation_ready=False,
        issues=[SimpleNamespace(code="stale_preview", message="changed", blocking=True)],
    )
    report = build_validation_report(**values)
    assert report["status"] == "blocked"
    assert report["read_only_validation_ready"] is False
    assert report["stages"]["database_freshness"]["ready"] is False
    assert "stale_preview" in {item["code"] for item in report["blockers"]}


def test_policy_drift_blocks_report_and_invariants_may_be_unevaluated():
    values = _healthy()
    values["policy_binding"] = Obj(
        binding_ready=False,
        issues=[SimpleNamespace(code="auction_policy_drift", message="changed", blocking=True)],
    )
    values["invariants"] = None
    report = build_validation_report(**values)
    codes = {item["code"] for item in report["blockers"]}
    assert report["status"] == "blocked"
    assert "auction_policy_drift" in codes
    assert "invariants_not_evaluated" in codes


def test_missing_purchase_trigger_shape_is_reported_separately():
    values = _healthy()
    values["prepared"] = Obj(operation="purchase_item", validation_ready=True, issues=[])
    values["readiness"] = dict(_readiness(), legacy_purchase_prerequisites_present=False)
    report = build_validation_report(**values)
    assert report["stages"]["schema_readiness"]["ready"] is False
    assert "legacy_purchase_prerequisites_missing" in {item["code"] for item in report["blockers"]}


def test_unknown_environment_fails_closed():
    values = _healthy()
    values["environment"] = dict(_environment(), family="auto", is_active=False)
    report = build_validation_report(**values)
    codes = {item["code"] for item in report["blockers"]}
    assert "environment_not_active" in codes
    assert "environment_lineage_unknown" in codes
    assert report["execution_ready"] is False


def test_module_contains_no_mutation_or_commit_primitive():
    from pathlib import Path
    source = Path("src/workbench/server_admin/auction_house/validation_report.py").read_text(encoding="utf-8").upper()
    assert "UPDATE AUCTION_HOUSE" not in source
    assert "INSERT INTO AUCTION_HOUSE" not in source
    assert "DELETE FROM AUCTION_HOUSE" not in source
    assert ".COMMIT(" not in source
