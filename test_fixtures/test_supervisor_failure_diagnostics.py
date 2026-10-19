"""Modern/legacy supervisor failure summaries remain read-only and fail-closed."""
from workbench.server_admin.feature_testing.failure_diagnostics import failure_summary


def record(verdict="PASS", evidence=None):
    return {"run_id": "run-1", "feature_id": "moghancement", "case_id": "MOG-09",
            "stage": "key_item", "verdict": verdict, "observed_at": "2026-10-19T00:00:00Z",
            "evidence": evidence if evidence is not None else {"assertions": [{"ok": True}]}}


def test_modern_failed_assertion_detected_despite_recorded_pass():
    result = failure_summary(record(evidence={"assertions": [
        {"name": "aura", "ok": True},
        {"name": "inventory", "ok": False, "expected": [1], "observed": [2]}]}))
    assert result["verdict"] == "PASS"  # Never rewrite historical evidence.
    assert result["assertion_failures_total"] == 1
    assert result["assertions"][0]["verdict"] == "FAIL"
    assert result["assertions"][0]["id"] == '"inventory"'


def test_legacy_evaluation_retained_for_failed_record():
    result = failure_summary(record("FAIL", {"evaluation": {"reason": "wrong item"}}))
    assert result["assertion_failures_total"] == 0
    assert "wrong item" in result["evaluation"]["reason"]


def test_clean_pass_not_reported():
    assert failure_summary(record()) is None


def test_malformed_assertions_are_not_silently_green():
    result = failure_summary(record(evidence={"assertions": "corrupt"}))
    assert result["incomplete_evidence"] is True
    assert result["assertion_failures_total"] == 0


def test_capped_failure_payload():
    assertions = [{"id": i, "verdict": "FAIL", "observed": "x" * 10000} for i in range(40)]
    result = failure_summary(record(evidence={"assertions": assertions}))
    assert result["assertion_failures_total"] == 40
    assert len(result["assertions"]) == 20
    assert result["assertions_truncated"]
    assert len(result["assertions"][0]["observed"]) < 600
