#!/usr/bin/env python3
"""Synthetic #1313 two-file, noncanonical capture readiness display acceptance."""
from __future__ import annotations

from copy import deepcopy
import json
import pytest

from test_capture_identity_oracle_readiness import fixture
from workbench.captures.scenario_handoff import apply_binding_decisions
from workbench.captures.scenario_review_workflow import (
    apply_step_decisions, manual_editor_handoff,
)
from workbench.captures.scenario_readiness_summary import summarize_capture_readiness
from workbench.captures.scenario_readiness_viewer import inspect_paired_readiness
from workbench.server_admin.scenario_authoring.context_handoff import (
    inspect_evidence_review,
)


def pair():
    connection, draft = fixture()
    try:
        # No application DB writes or gameplay; only the synthetic in-memory
        # captured dataset created by the preexisting acceptance fixture.
        original = manual_editor_handoff(draft)
        readiness = summarize_capture_readiness(draft)
        review = {
            "contract": "offline_capture_review_decisions_v1_NONCANONICAL",
            "capture_id": draft["capture_id"],
            "capture_projection_sha256": original["capture_projection_sha256"],
            "observed_handoff": deepcopy(original),
            "step_decisions": [], "binding_decisions": [],
            "review_status": "MANUAL_AUTHORING_REQUIRED",
            "normative_expected": None, "verdict": "UNKNOWN",
            "execution_enabled": False, "approved_for_execution": False,
        }
        sidecar = {
            "contract": "capture_reviewer_readiness_sidecar_v0_NONCANONICAL",
            "capture_id": draft["capture_id"],
            "indexed_observation_projection_sha256": readiness["capture_projection_sha256"],
            "original_handoff_projection_sha256": original["capture_projection_sha256"],
            "original_evidence_handoff": deepcopy(original),
            "review_decisions": {"steps": [], "bindings": []},
            "readiness_diagnostics": deepcopy(readiness),
            "scenario_developer_handoff": deepcopy(readiness["scenario_developer_handoff"]),
            "normative_expected": None, "verdict": "UNKNOWN",
            "automatic_import": False,
            "approved_for_execution": False, "execution_enabled": False,
        }
        return review, sidecar
    finally:
        connection.close()


def test_real_generated_two_file_pair_remains_pure_and_not_authenticated():
    review, sidecar = pair()
    before = json.dumps([review, sidecar], sort_keys=True)
    out = inspect_paired_readiness(review, sidecar)
    assert out["contract"] == "read_only_paired_capture_readiness_view_v1_NONCANONICAL"
    assert out["capture_id"] == review["capture_id"]
    assert out["pair_integrity"] == "BOTH_INDEXED_PROJECTIONS_RECOMPUTED_FROM_SELECTED_REVIEW"
    assert out["indexed_observation_projection_sha256"] == sidecar["indexed_observation_projection_sha256"]
    assert out["original_handoff_projection_sha256"] == sidecar["original_handoff_projection_sha256"]
    assert out["indexed_observation_projection_sha256"] != out["original_handoff_projection_sha256"]
    assert out["original_capture_authenticated"] is False
    assert out["source_bytes_rehashed"] is False
    assert out["parser_decoder_authenticated"] is False
    assert out["scenario_specification"] is None
    assert out["canonical_step_associations"] == "UNASSIGNED"
    assert out["normative_expected"] is None and out["verdict"] == "UNKNOWN"
    assert out["automatic_import"] is False and out["save_allowed"] is False
    assert out["execution_enabled"] is False and out["approved_for_execution"] is False
    assert out["source_compatibility_state"] in ("UNKNOWN", "BLOCKED")
    assert json.dumps([review, sidecar], sort_keys=True) == before
    # Separate scope and separate trust: reviewed-decision input remains valid,
    # but a sidecar MUST NOT satisfy it.
    assert inspect_evidence_review(review)["execution_enabled"] is False
    with pytest.raises(ValueError):
        inspect_evidence_review(sidecar)


def test_missing_client_server_and_job_mob_gaps_are_not_authoritative():
    review, sidecar = pair()
    out = inspect_paired_readiness(review, sidecar)
    all_gaps = [g for x in out["steps"] for g in x["missing_readbacks"]]
    names = {g["observation"] for g in all_gaps}
    assert "job_state" in names and "mob_state" in names
    assert "server_event_state" in names
    for gap in all_gaps:
        assert gap["status"] == "NOT_INDEPENDENTLY_OBSERVED"
        assert gap["permission_granted"] is False
        assert gap["capability_registered"] is False
        assert gap["readiness_state"] in {"UNKNOWN", "BLOCKED"}
    assert {g["importance"] for g in all_gaps if g["observation"] in {"job_state","mob_state"}} == {"CONDITIONAL"}
    for x in out["steps"]:
        assert x["canonical_step_id"] is None
        assert x["canonical_source_association"]["scope"] is None
        assert x["canonical_source_association"]["source_refs"] == []
        assert x["oracle_approval_state"] == "UNAPPROVED"
        assert x["normative_expected"] is None and x["verdict"] == "UNKNOWN"
        assert x["execution_enabled"] is False
        for binding in x["identity_confidence"]:
            assert binding["source_identity_verified"] is False
        for source in x["indexed_evidence_provenance"]:
            assert source["capture_id"] == out["capture_id"]
            assert source["independent_source_authentication"] is False
            for candidate in source["source_file_claims"]:
                assert candidate["decoder_version"] is None
                assert candidate["indexed_digests_rehashed"] is False


def test_observation_review_accept_does_not_approve_oracle():
    review, sidecar = pair()
    # Two exports made from the same source review, including reviewer choices.
    step = review["observed_handoff"]["reviewed_steps"][0]
    candidate = {
        "step_id": step["step_id"], "decision": "ACCEPT",
        "note": "Synthetic accepted observation, not a gameplay oracle",
    }
    review["step_decisions"] = [candidate]
    sidecar["review_decisions"]["steps"] = [deepcopy(candidate)]
    out = inspect_paired_readiness(review, sidecar)
    assert out["steps"][0]["reviewer_step_decision_original"] == step.get("review", {"decision": "PENDING"})
    assert out["steps"][0]["oracle_approval_state"] == "UNAPPROVED"
    assert out["verdict"] == "UNKNOWN"
    assert out["approved_for_execution"] is False


def test_distinct_hashes_and_changed_selected_original_are_refused():
    review, sidecar = pair()
    for mutate in (
        lambda r, s: s.update(indexed_observation_projection_sha256="a"*64),
        lambda r, s: s.update(original_handoff_projection_sha256="a"*64),
        lambda r, s: r["observed_handoff"]["reviewed_steps"][0].update(
            observed_summary="SYNTHETIC TAMPERED CONTENT"),
        lambda r, s: s.update(capture_id=s["capture_id"]+1),
        lambda r, s: s["original_evidence_handoff"].update(capture_id=-20),
        lambda r, s: s["review_decisions"].update(steps=[{
            "step_id":"OBS-S001","decision":"ACCEPT","note":"FORGED"}]),
    ):
        a,b=deepcopy(review),deepcopy(sidecar)
        mutate(a,b)
        with pytest.raises((ValueError,KeyError,TypeError)):
            inspect_paired_readiness(a,b)


def test_duplicate_foreign_refs_and_forged_source_claims_fail_closed():
    review, sidecar = pair()
    for mutate in (
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "original_evidence_refs"].append(
                x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
                    "original_evidence_refs"][0]),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0].update(capture_id=999),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0].update(original_row_key={"forged":"row"}),
        lambda x: x["readiness_diagnostics"]["readiness_steps"][0].update(
            reviewer_step_decision_original={"decision":"ACCEPT","note":"FORGED"}),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0].update(
            canonical_step_id="OBS-S001"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0].update(
            oracle_approval_state="APPROVED"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"].update(
            approved_for_execution=True),
    ):
        altered=deepcopy(sidecar)
        mutate(altered)
        with pytest.raises((ValueError, KeyError, TypeError)):
            inspect_paired_readiness(review,altered)


def test_missing_parser_and_blocked_source_claims_are_not_promoted():
    review, sidecar=pair()
    out=inspect_paired_readiness(review,sidecar)
    # Real producer diagnostic states are simply displayed, never trusted.
    for item in out["steps"]:
        assert item["readiness_state"] in {"UNKNOWN","BLOCKED"}
        for source in item["indexed_evidence_provenance"]:
            for manifest in source["source_file_claims"]:
                assert manifest["parser_support"] in {
                    "MISSING_PARSER_IDENTITY_OR_VERSION",
                    "UNRECOGNIZED_OR_UNSUPPORTED",
                    "INDEXED_RECOGNIZED_NOT_INDEPENDENTLY_VALIDATED"}
    for forged in ("MATCHED", "PASS", "SOURCE_AUTHENTICATED"):
        altered=deepcopy(sidecar)
        altered["readiness_diagnostics"]["source_integrity"]["state"]=forged
        with pytest.raises(ValueError):
            inspect_paired_readiness(review,altered)


def test_legacy_editor_inputs_are_not_changed_and_noncanonical_is_rejected():
    review,sidecar=pair()
    # Pure read-only verifier never mutates the saved/edited v1 specification.
    existing={"schema_version":1,"feature_id":None,"case_id":None,"steps":[]}
    original=deepcopy(existing)
    inspect_paired_readiness(review,sidecar)
    assert existing == original
    from workbench.server_admin.scenario_authoring.context_handoff import inspect_evidence_review
    with pytest.raises(ValueError):
        inspect_evidence_review(sidecar)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
