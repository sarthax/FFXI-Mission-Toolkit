"""R8 #1255: offline compatibility probes, NOT a cross-repository execution schema.

Only invoke existing Toolkit Python evaluators, validators and preflight.
No process, MCP call, local DB write, gameplay, lease or network activity.
Headless #105 remains unapproved; never treat these examples as transport.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_fixtures.test_feature_testing_normalized_evidence import sample
from workbench.server_admin.feature_testing.assertion_engine import evaluate
from workbench.server_admin.feature_testing.execution_preflight import preflight
from workbench.server_admin.feature_testing.importer import validate_report
from workbench.server_admin.feature_testing.normalized_evidence import evaluate_imported_mog09
from workbench.server_admin.feature_testing.results import VERDICTS
from workbench.server_admin.feature_testing.scenario_contract_v2 import compatibility_report
from workbench.server_admin.feature_testing.test_specifications import (
    specification, specifications, validate_spec,
)

ROOT = Path(__file__).resolve().parent
MATRIX = json.loads(
    (ROOT / "r8_execution_boundary_matrix_synthetic.json").read_text(encoding="utf-8")
)
VECTORS = {v["id"]: v for v in MATRIX["vectors"]}


def _expect(name: str, state: str) -> None:
    assert VECTORS[name]["expected"] == state
    assert MATRIX["synthetic"] is True
    assert MATRIX["not_an_execution_protocol"] is True
    assert MATRIX["not_an_importer_report"] is True
    assert MATRIX["runtime_dispatch_allowed"] is False


def _row() -> dict:
    return {
        "run_id": "synthetic-run-001",
        "feature_id": "moghancement",
        "case_id": "MOG-09",
        "stage": "key_item",
        "verdict": "BLOCKED",
        "observed_at": "2026-10-20T00:00:00Z",
        "dsp_commit": "a" * 40,
        "headless_commit": "b" * 40,
        "toolkit_commit": "c" * 40,
        # WP4a: a BLOCKED import must say why; OTHER makes no claim about the cause.
        "evidence": {"synthetic": True, "readback": "unavailable", "reason_class": "OTHER"},
    }


def _catalog() -> dict:
    return {"features": [{"id": "moghancement", "cases": [{"id": "MOG-09"}]}]}


def test_matrix_is_a_ten_case_noncanonical_gate_not_a_protocol():
    assert len(VECTORS) == len(MATRIX["vectors"]) == 10
    assert all(v["fact"] and not v["fact"].startswith("PASS observed")
               for v in MATRIX["vectors"])
    assert {v["expected"] for v in MATRIX["vectors"]} == {
        "UNKNOWN", "BLOCKED", "NOT_IMPLEMENTED",
    }
    assert specification("moghancement", "MOG-09")["runner"] == "xiheadless_observation_v1"
    assert specification("inventory_observation", "INV-OBS-01")["runner"] == "unassigned"
    assert len(specifications()) == 2


def test_reported_success_is_unverified_not_supervised_acceptance():
    _expect("supervised_observation_reported_pass", "UNKNOWN")
    imported_claim = sample()
    result = evaluate_imported_mog09(imported_claim)
    assert result["evaluation"]["verdict"] == "PASS"
    assert result["normalization"]["evidence_authenticated"] is False
    assert result["normalization"]["execution_enabled"] is False
    assert result["recorded_verdict"] == "PASS"
    assert result["evaluation"]["source"] == "deterministic_evaluation_of_supplied_unverified_observations"


def test_missing_preconditions_are_not_auto_satisfied(monkeypatch):
    _expect("missing_preconditions", "BLOCKED")
    for key in (
        "MISSION_TOOLKIT_TEST_HEADLESS_ROOT",
        "MISSION_TOOLKIT_TEST_RESULTS_DB",
        "MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS",
        "MISSION_TOOLKIT_SUPERVISOR_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    actual = preflight("moghancement", "MOG-09")
    assert actual["ready_for_operator_review"] is False
    assert actual["launch_implemented"] is False
    assert actual["execution_enabled"] is False
    assert any(not check["ok"] for check in actual["checks"])


def test_missing_authoritative_readback_remains_blocked():
    _expect("missing_authoritative_readback", "BLOCKED")
    record = sample()
    record["evidence"]["assertions"].pop()
    result = evaluate_imported_mog09(record)
    assert result["evaluation"]["verdict"] == "BLOCKED"
    assert {"client_safe", "db_safe"} <= set(result["normalization"]["missing_fields"])


def test_cancellation_acknowledgment_is_not_a_toolkit_report():
    _expect("cancellation", "UNKNOWN")
    # Current Headless MCP result-like message, SYNTHETIC. A cancellation
    # request alone does not prove the terminal task/evidence state.
    mcp_ack = {"ok": True, "accepted": True, "outcome": "accepted",
               "operation_id": "synthetic-cancel-operation"}
    assert "completed" not in mcp_ack
    with pytest.raises(ValueError, match="schema"):
        validate_report(mcp_ack, _catalog())


def test_partial_evidence_cannot_satisfy_missing_assertion():
    _expect("partial_evidence", "BLOCKED")
    record = sample()
    record["evidence"]["assertions"] = [
        a for a in record["evidence"]["assertions"]
        if a["name"] != "client bag equals persisted char_inventory location 0"
    ]
    rechecked = evaluate_imported_mog09(record)
    assert rechecked["evaluation"]["verdict"] == "BLOCKED"
    assert {"client_bag", "db_bag"} <= set(rechecked["normalization"]["missing_fields"])


def test_conflicting_attempt_ids_have_no_supported_v1_identity_field():
    _expect("conflicting_attempt_ids", "BLOCKED")
    row = _row()
    assert "attempt_id" not in row and "operation_id" not in row
    with pytest.raises(ValueError, match="duplicate result identity"):
        validate_report({"schema_version": 1, "results": [row, deepcopy(row)]},
                        _catalog())
    with pytest.raises(ValueError, match="result fields"):
        validate_report({"schema_version": 1, "results": [
            {**row, "attempt_id": "synthetic-attempt-2"}
        ]}, _catalog())


def test_design_only_spec_cannot_be_upgraded_to_verified_mutating_runner():
    _expect("unsupported_mutation", "BLOCKED")
    spec = deepcopy(specification("inventory_observation", "INV-OBS-01"))
    assert spec["execution_status"] == "design_only"
    spec.update(runner="xiheadless_observation_v1", execution_status="verified_runner")
    with pytest.raises(ValueError, match="no verified implementation"):
        validate_spec(spec)
    assert preflight("inventory_observation", "INV-OBS-01")["execution_enabled"] is False


def test_stale_canonical_source_revision_blocks_but_grants_nothing():
    _expect("stale_source_revision", "BLOCKED")
    spec = json.loads(
        (ROOT / "r7_contract_v2_source_associations_valid_synthetic.json")
        .read_text(encoding="utf-8")
    )
    ref = spec["contract_v2"]["sources"][0]["ref"]
    spec["contract_v2"]["sources"][0].update(revision="a" * 40, sha256="b" * 64)
    outcome = compatibility_report(
        spec, observed_sources={ref: {"revision": "c" * 40, "sha256": "b" * 64}}
    )
    assert outcome["state"] == "BLOCKED"
    assert outcome["execution_enabled"] is False
    assert outcome["independent_verification"] == "NOT_ESTABLISHED"


def test_repeated_import_is_not_idempotent_just_because_v1_validates():
    _expect("repeated_evidence_import", "NOT_IMPLEMENTED")
    row = _row()
    report = {"schema_version": 1, "results": [row]}
    assert validate_report(report, _catalog()) == [row]
    assert validate_report(report, _catalog()) == [row]
    # validate_report checks only one batch. It returns no replay decision,
    # attempt ID, evidence digest, or reconciliation key. #1202 owns replay.
    # WP4a (owner decision): UNKNOWN is now a stored verdict so an unestablished result can be recorded
    # explicitly. It is still never PASS, and a PASS row still needs assertions and observations.
    assert "UNKNOWN" in VERDICTS
    with pytest.raises(ValueError, match="PASS requires assertions and observations"):
        validate_report({"schema_version": 1, "results": [{**row, "verdict": "PASS"}]}, _catalog())
    assert "attempt_id" not in row
    assert "evidence_digest" not in row


def test_command_accepted_is_not_completed_and_cannot_become_pass():
    _expect("command_acceptance_only", "UNKNOWN")
    admission = {"ok": True, "accepted": True, "outcome": "accepted",
                 "operation_id": "synthetic-task"}
    assert admission["accepted"] is True and "completed" not in admission
    with pytest.raises(ValueError, match="schema"):
        validate_report(admission, _catalog())
    spec = specification("moghancement", "MOG-09")
    evaluated = evaluate(spec, {})
    assert evaluated["verdict"] == "BLOCKED"
    assert evaluated["execution_enabled"] is False
