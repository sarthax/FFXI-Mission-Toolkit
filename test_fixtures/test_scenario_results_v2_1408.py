#!/usr/bin/env python3
"""Deterministic safety checks for seven synthetic/unavailable results cases; no runner."""
import json
from pathlib import Path

DATA = json.loads((Path(__file__).with_name("scenario_results_v2_1408.json")).read_text())
ALLOWED_LIFECYCLE = {"UNKNOWN", "COMPLETED", "NOT_STARTED", "CANCEL_REQUEST_ACCEPTED"}
ALLOWED_VERDICTS = {"PASS", "FAIL", "BLOCKED", "UNKNOWN"}

def comparable(left, right):
    """Only independently grounded, identical source/run/revision pairs can be compared."""
    keys = ("run_id", "attempt_id", "scenario_revision")
    return (all(left.get(k) is not None and right.get(k) is not None for k in keys)
            and all(left.get(k) == right.get(k) for k in keys)
            and left.get("source_revisions") == right.get("source_revisions")
            and left.get("source_revisions") is not None
            and all(left["source_revisions"].get(k) is not None for k in ("toolkit", "xiheadless", "dsp"))
            and not left.get("conflicting_receipts") and not right.get("conflicting_receipts"))

def validate(case):
    assert case["task_lifecycle"] in ALLOWED_LIFECYCLE
    assert case["verdict"] in ALLOWED_VERDICTS
    assert case["comparison"] == "NOT_COMPARABLE"
    assert case["run_id"] is None and case["attempt_id"] is None
    assert case["execution_started_at"] is None
    assert all(value is None for value in case["source_revisions"].values())
    assert case["fixture_kind"] != "SOURCE_BACKED_RUN_UNAVAILABLE" or (
        case["verdict"] == "UNKNOWN" and case["missing_evidence_reason"] and not case["steps"])
    assert case["task_lifecycle"] != "CANCEL_REQUEST_ACCEPTED" or case["verdict"] == "UNKNOWN"
    assert case["task_lifecycle"] != "COMPLETED" or case["verdict"] != "PASS"
    assert case["verdict"] != "FAIL" or any(
        step["observed_typed"] is not None and step["evidence_refs"] for step in case["steps"])
    if case.get("conflicting_receipts"):
        assert case["verdict"] == "UNKNOWN"
        assert len({(x["run_id"], x["revision"], x["digest"]) for x in case["conflicting_receipts"]}) > 1
    for step in case["steps"]:
        assert step["human_action"] and step["expected_description"]
        assert step["verdict"] in ALLOWED_VERDICTS
        assert step["oracle_review_state"] != "APPROVED"
        assert step["observed_typed"] is not None or step["missing_evidence_reason"]
        for ref in step["evidence_refs"]:
            assert ref["kind"] == "SYNTHETIC_RECEIPT" and ref["uri"].startswith("fixture://")
    return True

def main():
    assert DATA["status"] == "TEST_ONLY_NON_EXECUTABLE"
    cases = DATA["cases"]
    kinds = {x["fixture_kind"] for x in cases}
    assert len(cases) == 7 and len(kinds) == 7 and len({x["id"] for x in cases}) == 7
    for case in cases:
        validate(case)
        assert not comparable(case, case)
    by_kind = {x["fixture_kind"]: x for x in cases}
    assert by_kind["CONTRADICTED_EXPECTATION"]["verdict"] == "FAIL"
    assert by_kind["MISSING_READBACK"]["verdict"] == "UNKNOWN"
    assert by_kind["PREFLIGHT_BLOCKED"]["verdict"] == "BLOCKED"
    assert by_kind["CANCELLATION_ACK"]["task_lifecycle"] == "CANCEL_REQUEST_ACCEPTED"
    assert by_kind["PROVENANCE_CONFLICT"]["verdict"] == "UNKNOWN"
    assert by_kind["ZERO_HISTORY"]["missing_evidence_reason"] == "NO_RECORDED_RESULTS"
    assert by_kind["SOURCE_BACKED_RUN_UNAVAILABLE"]["run_id"] is None
    # Negative mutations must fail rather than pass merely due to lifecycle or fake metadata.
    for kind, key, value in (("MISSING_READBACK", "verdict", "PASS"),
                              ("CANCELLATION_ACK", "verdict", "PASS"),
                              ("SOURCE_BACKED_RUN_UNAVAILABLE", "run_id", "invented-run"),
                              ("PROVENANCE_CONFLICT", "verdict", "PASS")):
        corrupted = dict(by_kind[kind], **{key:value})
        try:
            validate(corrupted)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"mutation incorrectly accepted: {kind} {key}")
    print("scenario results v2: seven safe fixture classes PASS; no native execution")

if __name__ == "__main__":
    main()
