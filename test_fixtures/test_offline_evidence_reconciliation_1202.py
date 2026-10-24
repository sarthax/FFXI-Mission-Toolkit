"""SYNTHETIC offline-only regression; never an authenticated Headless result."""
from copy import deepcopy

import pytest

from workbench.server_admin.feature_testing.offline_evidence_reconciliation import (
    FORMAT, OfflineEvidenceLedger, canonical_evidence_digest,
)


def receipt(**overrides):
    evidence = overrides.pop("evidence", {"reported": "synthetic_observation_a"})
    row = {
        "format": FORMAT, "run_id": "synthetic-run-01",
        "execution_id": "synthetic-execution-01", "attempt": 1,
        "operation_id": "synthetic-operation-01", "receipt_id": "synthetic-receipt-01",
        "feature_id": "moghancement", "case_id": "MOG-09",
        "definition_revision": "synthetic-rev-1",
        "phase": "PARTIAL", "operation_state": "running",
        "evidence_complete": False, "reported_verdict": "PASS",
        "evidence": evidence, "missing_artifacts": ["server_readback"],
        "provenance": {"observer": "synthetic-fixture", "original_ref": "synthetic:input",
                       "source_authenticated": False, "oracle_approved": False},
    }
    row.update(overrides)
    row["evidence_digest"] = canonical_evidence_digest(evidence)
    return row


def terminal(start, **overrides):
    row = deepcopy(start)
    row.update(receipt_id="synthetic-receipt-terminal", phase="TERMINAL",
               operation_state="completed", evidence_complete=True,
               missing_artifacts=[], evidence={"reported": "terminal"})
    row.update(overrides)
    row["evidence_digest"] = canonical_evidence_digest(row["evidence"])
    return row


def test_exact_replay_is_no_change_and_original_is_detached():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    assert ledger.ingest(first)["status"] == "FIRST_SEEN"
    assert ledger.ingest(deepcopy(first))["status"] == "NO_CHANGE"
    snap = ledger.snapshot(first["run_id"], first["execution_id"], 1)
    assert len(snap["operations"][first["operation_id"]]["receipts"]) == 1
    assert snap["authoritative_gameplay_verdict"] == "UNKNOWN"
    assert snap["v1_import_eligible"] is False
    assert snap["durable"] is False
    snap["operations"][first["operation_id"]]["receipts"][0]["evidence"]["reported"] = "tampered"
    assert ledger.snapshot(first["run_id"], first["execution_id"], 1)[
        "operations"][first["operation_id"]]["receipts"][0]["evidence"] == first["evidence"]
    first["evidence"]["reported"] = "caller-mutation"
    assert ledger.snapshot("synthetic-run-01", "synthetic-execution-01", 1)[
        "operations"]["synthetic-operation-01"]["receipts"][0]["evidence"]["reported"] == "synthetic_observation_a"


def test_conflicting_digest_same_identity_is_blocked_without_overwrite():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    assert ledger.ingest(first)["status"] == "FIRST_SEEN"
    edited = receipt(evidence={"reported": "conflicting_report"})
    result = ledger.ingest(edited)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "IDENTITY_DIGEST_CONFLICT"
    assert len(ledger.snapshot("synthetic-run-01", "synthetic-execution-01", 1)[
        "operations"]["synthetic-operation-01"]["receipts"]) == 1


def test_claimed_digest_tampering_rejected_before_recording():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    first["evidence"]["reported"] = "tampered"
    assert ledger.ingest(first)["status"] == "BLOCKED"
    assert ledger.snapshot("synthetic-run-01", "synthetic-execution-01", 1) is None


def test_partial_then_terminal_preserves_both_provenances_without_pass():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    done = terminal(first)
    assert ledger.ingest(first)["status"] == "FIRST_SEEN"
    assert ledger.ingest(done)["status"] == "PARTIAL_TO_TERMINAL"
    assert ledger.ingest(done)["status"] == "NO_CHANGE"
    op = ledger.snapshot("synthetic-run-01", "synthetic-execution-01", 1)[
        "operations"]["synthetic-operation-01"]
    assert [x["phase"] for x in op["receipts"]] == ["PARTIAL", "TERMINAL"]
    assert [x["evidence_digest"] for x in op["receipts"]] == [
        first["evidence_digest"], done["evidence_digest"]
    ]
    assert op["evidence_complete_claim"] is True
    assert op["reported_verdict"] == "PASS"
    assert op["authoritative_gameplay_verdict"] == "UNKNOWN"
    assert op["oracle_approved"] is False
    assert op["source_authenticated"] is False


@pytest.mark.parametrize("state", ["cancelled", "failed", "interrupted"])
def test_cancel_failure_and_interruption_do_not_promote_reported_pass(state):
    ledger = OfflineEvidenceLedger()
    first = receipt()
    assert ledger.ingest(first)["status"] == "FIRST_SEEN"
    done = terminal(first, operation_state=state, evidence_complete=False,
                    missing_artifacts=["terminal_artifact", "cleanup_record"])
    assert ledger.ingest(done)["status"] == "PARTIAL_TO_TERMINAL"
    op = ledger.snapshot(first["run_id"], first["execution_id"], 1)["operations"][
        first["operation_id"]]
    assert op["operation_state"] == state
    assert op["missing_artifacts"] == ["terminal_artifact", "cleanup_record"]
    assert op["authoritative_gameplay_verdict"] == "UNKNOWN"


def test_cancelled_partial_remains_partial_and_cannot_be_reinterpreted_as_success():
    ledger = OfflineEvidenceLedger()
    r = receipt(operation_state="cancelled", reported_verdict="PASS")
    assert ledger.ingest(r)["status"] == "FIRST_SEEN"
    op = ledger.snapshot(r["run_id"], r["execution_id"], 1)["operations"][r["operation_id"]]
    assert op["phase"] == "PARTIAL"
    assert op["authoritative_gameplay_verdict"] == "UNKNOWN"


def test_terminal_change_and_late_partial_cannot_overwrite():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    done = terminal(first)
    ledger.ingest(first)
    ledger.ingest(done)
    competing = terminal(first, receipt_id="synthetic-terminal-two",
                         evidence={"reported": "opposite_terminal"})
    assert ledger.ingest(competing)["reason"] == "TERMINAL_DIGEST_CONFLICT"
    late = receipt(receipt_id="synthetic-late-partial", evidence={"reported": "late"})
    assert ledger.ingest(late)["reason"] == "TERMINAL_IMMUTABLE"
    assert len(ledger.snapshot(first["run_id"], first["execution_id"], 1)[
        "operations"][first["operation_id"]]["receipts"]) == 2


def test_atomic_batch_conflict_commits_nothing():
    ledger = OfflineEvidenceLedger()
    original = receipt()
    ledger.ingest(original)
    later = receipt(receipt_id="synthetic-intermediate",
                    evidence={"reported": "progress"})
    conflict = receipt(evidence={"reported": "tampered_same_receipt"})
    outcome = ledger.ingest_many([later, conflict])
    assert outcome["status"] == "BLOCKED"
    assert outcome["reason"] == "IDENTITY_DIGEST_CONFLICT"
    assert len(ledger.snapshot(original["run_id"], original["execution_id"], 1)[
        "operations"][original["operation_id"]]["receipts"]) == 1


def test_multiple_operations_but_no_attempt_identity_conflation():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    other = receipt(operation_id="synthetic-operation-02",
                    receipt_id="synthetic-operation-02-receipt")
    assert ledger.ingest_many([first, other])["status"] == "ACCEPTED"
    assert len(ledger.snapshot(first["run_id"], first["execution_id"], 1)["operations"]) == 2
    mismatch = receipt(operation_id="synthetic-operation-03",
                       receipt_id="synthetic-receipt-other", definition_revision="different")
    assert ledger.ingest(mismatch)["reason"] == "ATTEMPT_DEFINITION_CONFLICT"
    reused = receipt(operation_id="synthetic-operation-03")
    assert ledger.ingest(reused)["reason"] == "IDENTITY_DIGEST_CONFLICT"
    different_attempt = receipt(attempt=2)
    assert ledger.ingest(different_attempt)["status"] == "FIRST_SEEN"
    assert ledger.snapshot(first["run_id"], first["execution_id"], 2) is not None


@pytest.mark.parametrize("change", [
    {"format": "xi-test-execution/2"}, {"format": "toolkit-offline-receipt/2"},
    {"attempt": True}, {"attempt": 0}, {"operation_state": "unknown"},
    {"phase": "DONE"}, {"reported_verdict": "SUCCESS"},
    {"evidence_complete": 1}, {"missing_artifacts": ["same", "same"]},
    {"phase": "TERMINAL"},  # running state cannot be a terminal event
    {"provenance": {"observer": "fixture", "original_ref": "ref",
                    "source_authenticated": True, "oracle_approved": False}},
    {"provenance": {"observer": "fixture", "original_ref": "ref",
                    "source_authenticated": False, "oracle_approved": True}},
])
def test_invalid_or_unapproved_receipts_fail_closed(change):
    ledger = OfflineEvidenceLedger()
    assert ledger.ingest(receipt(**change))["status"] == "BLOCKED"
    assert ledger.snapshot("synthetic-run-01", "synthetic-execution-01", 1) is None


def test_unknown_core_field_and_unserializable_payload_are_blocked():
    ledger = OfflineEvidenceLedger()
    x = receipt()
    x["unsupported_core_field"] = True
    assert ledger.ingest(x)["status"] == "BLOCKED"
    bad = receipt()
    bad["evidence"] = {"not_json": set([1])}
    assert ledger.ingest(bad)["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="offline limit"):
        canonical_evidence_digest({"text": "x" * 40000})
    large = receipt()
    large["evidence"] = {"text": "x" * 40000}
    assert ledger.ingest(large)["status"] == "BLOCKED"


def test_duplicate_digest_with_different_receipt_is_not_silent_second_event():
    ledger = OfflineEvidenceLedger()
    first = receipt()
    assert ledger.ingest(first)["status"] == "FIRST_SEEN"
    dup = receipt(receipt_id="synthetic-receipt-different")
    assert ledger.ingest(dup)["reason"] == "DUPLICATE_DIGEST_DIFFERENT_RECEIPT"
    assert len(ledger.snapshot(first["run_id"], first["execution_id"], 1)[
        "operations"][first["operation_id"]]["receipts"]) == 1


def test_no_legacy_v1_importer_or_database_side_effect(tmp_path):
    from workbench.server_admin.feature_testing.importer import import_report
    from workbench.server_admin.feature_testing.results import recent_results
    ledger = OfflineEvidenceLedger()
    assert ledger.ingest(receipt())["status"] == "FIRST_SEEN"
    # Reconciler did not create a durable store or project UNKNOWN to v1 PASS.
    assert list(tmp_path.iterdir()) == []
    # Existing v1 importer still rejects unsupported version independently.
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"features":[{"id":"moghancement","cases":[{"id":"MOG-09"}]}]}')
    report = tmp_path / "report.json"
    report.write_text('{"schema_version":2,"results":[]}')
    db = tmp_path / "legacy.sqlite"
    with pytest.raises(ValueError, match="unsupported report schema"):
        import_report(db, catalog, report)
    assert recent_results(db) == []
