"""R8 #1325/#1198 synthetic contract guards ONLY; never exercise a runner/importer.

These tests validate proposed design invariants on explicitly fake records.
They do not establish a deployed MCP endpoint or authenticate game evidence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

FILE = Path(__file__).with_name("r8_evidence_summary_vectors_synthetic.json")
DATA = json.loads(FILE.read_text(encoding="utf-8"))
CASES = {v["id"]: v for v in DATA["examples"]}
ALLOWED_STATES = {"UNKNOWN", "BLOCKED"}
ALLOWED_DISPOSITIONS = {
    "DRAFT_UNTRUSTED", "REQUIRE_FRESH_EVIDENCE",
    "REFUSE_UNTIL_RECONCILED", "NO_CHANGE",
}
NONCANONICAL = "scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL"
PROPOSAL = "scenario_revision_proposal_v0_UNTRUSTED_DESIGN"


def classify(v: dict) -> tuple[str, str]:
    """Deterministic design-only triage; NOT a gameplay verdict evaluator."""
    attempt = v["attempt"]
    source = v["provenance"]
    evidence = v["evidence"]
    lifecycle = v["lifecycle"]
    if attempt["reconciliation"] == "IDENTITY_DIGEST_CONFLICT":
        return "BLOCKED", "REFUSE_UNTIL_RECONCILED"
    if attempt["reconciliation"] == "EXACT_REPLAY":
        return "UNKNOWN", "NO_CHANGE"
    if source["source_revision_assessment"] == "STALE":
        return "BLOCKED", "REQUIRE_FRESH_EVIDENCE"
    if (source["source_revision_assessment"] == "CONFLICT"
            or evidence["conflicting_observations"]):
        return "BLOCKED", "REFUSE_UNTIL_RECONCILED"
    if source["source_revision_assessment"] == "UNAUTHENTICATED_IDENTITY":
        return "BLOCKED", "DRAFT_UNTRUSTED"
    if (lifecycle["state"] != "COMPLETED"
            or not lifecycle["terminal_recorded"]
            or lifecycle["observation_completeness"] != "COMPLETE"):
        return "UNKNOWN", "DRAFT_UNTRUSTED"
    if evidence["missing_observations"]:
        return "BLOCKED", "DRAFT_UNTRUSTED"
    # A complete synthetic mismatch with unapproved oracles is NOT authority.
    return "UNKNOWN", "DRAFT_UNTRUSTED"


def preview_idempotency_key(v: dict) -> str:
    """Example content-addressed proposal key, distinct from existing importer IDs."""
    identity = v["triage"]["proposal"]["idempotency_identity"]
    payload = {
        "base_digest_claim": v["scenario"]["base_digest_claim"],
        "run_id": identity["run_id"],
        "attempt_id": identity["attempt_id"],
        "evidence_digest_claim": identity["evidence_digest_claim"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def validate_design_vector(v: dict) -> None:
    assert v["synthetic"] is True
    assert v["scenario"]["catalog_state"] == "DESIGN_ONLY"
    assert v["scenario"]["canonical_schema_version"] == 1
    assert all(v["attempt"][f] for f in ("run_id", "attempt_id", "evidence_digest_claim"))
    assert v["lifecycle"]["state"] in {"COMPLETED", "RUNNING", "CANCELLED", "INTERRUPTED"}
    assert v["lifecycle"]["observation_completeness"] in {"COMPLETE", "PARTIAL", "UNKNOWN"}
    assert v["lifecycle"]["cleanup_status"] in {
        "SYNTHETIC_REPORTED_COMPLETE", "UNKNOWN", "FAILED"
    }
    src = v["provenance"]
    assert src["original_source_ref"].startswith("synthetic://capture/")
    assert src["original_evidence_retained"] is True
    for name in ("source_bytes_authenticated", "decoder_authenticated",
                 "source_identity_verified"):
        assert src[name] is False
    ev = v["evidence"]
    assert ev["approved_oracles"] == []
    assert ev["independent_authority"] == "NOT_ESTABLISHED"
    assert ev["authoritative_gameplay_verdict"] in ALLOWED_STATES
    assert ev["reported_gameplay_verdict"] in {None, "FAIL", "PASS", "BLOCKED", "UNKNOWN"}
    for fact in ev["observed_facts"]:
        assert fact["source_ref"] == src["original_source_ref"]
        assert fact["observer"] in {"CLIENT", "SERVER", "CAPTURE"}
        assert fact["authentication"] == "UNVERIFIED"
    for hypothesis in ev["candidate_interpretations"]:
        assert hypothesis["status"] == "UNAPPROVED_HYPOTHESIS"
    for gap in ev["missing_observations"]:
        assert gap["permission_granted"] is False
        assert gap["reason"]
    for conflict in ev["conflicting_observations"]:
        assert conflict["reason"] and conflict["left_revision"] != conflict["right_revision"]
    proposal = v["triage"]["proposal"]
    assert proposal["contract"] == PROPOSAL
    assert proposal["status"] in ALLOWED_DISPOSITIONS
    assert proposal["status"] == v["triage"]["proposal_disposition"]
    assert proposal["base_revision"] == v["scenario"]["base_revision"]
    assert proposal["base_digest_claim"] == v["scenario"]["base_digest_claim"]
    assert proposal["idempotency_identity"] == {
        key: v["attempt"][key] for key in
        ("run_id", "attempt_id", "evidence_digest_claim")
    }
    assert proposal["required_reviews"] == [
        "HUMAN_REVIEW", "ORACLE_PROVENANCE", "SOURCE_REVISION"
    ]
    for name in ("canonical_write_allowed", "execution_allowed", "permission_grants_allowed"):
        assert proposal[name] is False
    for change in proposal["proposed_changes"]:
        assert change["before"] is None
        assert change["kind"] in {
            "REVIEW_NEGATIVE_CASE", "REQUEST_READBACK", "REFRESH_EVIDENCE",
            "REQUEST_PROVENANCE", "REVIEW_CANCELLATION_COVERAGE"
        }
        assert change["after"]
    if proposal["status"] in {"NO_CHANGE", "REFUSE_UNTIL_RECONCILED"}:
        assert not proposal["proposed_changes"]
    expected_state, expected_disposition = classify(v)
    assert (v["triage"]["expected_evidence_state"],
            v["triage"]["proposal_disposition"]) == (
                expected_state, expected_disposition
            )


class EvidenceSummaryDesignContractTests(unittest.TestCase):
    def test_envelope_is_not_an_importer_or_execution_contract(self):
        self.assertEqual(DATA["contract"], NONCANONICAL)
        self.assertTrue(DATA["synthetic"])
        for key in ("not_an_mcp_wire_protocol", "not_a_canonical_importer_report",
                    "not_authenticated_physical_source"):
            self.assertTrue(DATA[key])
        for key in ("canonical_mutation_allowed", "auto_oracle_approval_allowed",
                    "automatic_execution_allowed"):
            self.assertFalse(DATA[key])

    def test_all_eight_deterministic_failure_vectors(self):
        self.assertEqual(len(CASES), len(DATA["examples"]))
        self.assertEqual(set(CASES), {
            "complete-observed-mismatch", "missing-server-readback",
            "stale-capture", "conflicting-revisions", "exact-duplicate-attempt",
            "unauthenticated-source-identity", "incomplete-cancelled-execution",
            "conflicting-duplicate-attempt",
        })
        for v in DATA["examples"]:
            with self.subTest(v=v["id"]):
                validate_design_vector(v)

    def test_complete_observed_mismatch_is_not_approved_fail(self):
        v = CASES["complete-observed-mismatch"]
        self.assertTrue(v["lifecycle"]["terminal_recorded"])
        self.assertEqual(v["lifecycle"]["observation_completeness"], "COMPLETE")
        self.assertEqual({x["observer"] for x in v["evidence"]["observed_facts"]},
                         {"CLIENT", "SERVER"})
        self.assertEqual(v["evidence"]["reported_gameplay_verdict"], "FAIL")
        self.assertEqual(v["evidence"]["authoritative_gameplay_verdict"], "UNKNOWN")
        self.assertEqual(v["triage"]["proposal_disposition"], "DRAFT_UNTRUSTED")

    def test_missing_readback_and_cancellation_are_not_success(self):
        missing = CASES["missing-server-readback"]
        cancelled = CASES["incomplete-cancelled-execution"]
        self.assertEqual(classify(missing)[0], "BLOCKED")
        self.assertEqual(cancelled["lifecycle"]["cleanup_status"], "UNKNOWN")
        self.assertEqual(cancelled["lifecycle"]["state"], "CANCELLED")
        self.assertEqual(classify(cancelled)[0], "UNKNOWN")
        self.assertFalse(cancelled["lifecycle"]["observation_completeness"] == "COMPLETE")

    def test_duplicate_replay_is_noop_but_conflicting_identity_blocks(self):
        original = CASES["complete-observed-mismatch"]
        same = CASES["exact-duplicate-attempt"]
        conflict = CASES["conflicting-duplicate-attempt"]
        self.assertEqual(preview_idempotency_key(original),
                         preview_idempotency_key(same))
        self.assertNotEqual(preview_idempotency_key(original),
                            preview_idempotency_key(conflict))
        self.assertEqual(same["triage"]["proposal_disposition"], "NO_CHANGE")
        self.assertEqual(classify(conflict),
                         ("BLOCKED", "REFUSE_UNTIL_RECONCILED"))

    def test_forged_trust_and_permissions_rejected_by_design_validation(self):
        original = CASES["missing-server-readback"]
        mutations = [
            ("provenance", "source_bytes_authenticated", True),
            ("provenance", "source_identity_verified", True),
            ("evidence", "authoritative_gameplay_verdict", "PASS"),
            ("evidence", "independent_authority", "VERIFIED"),
        ]
        for part, key, value in mutations:
            with self.subTest(part=part, key=key):
                v = deepcopy(original)
                v[part][key] = value
                with self.assertRaises(AssertionError):
                    validate_design_vector(v)
        for key in ("canonical_write_allowed", "execution_allowed",
                    "permission_grants_allowed"):
            v = deepcopy(original)
            v["triage"]["proposal"][key] = True
            with self.assertRaises(AssertionError):
                validate_design_vector(v)

    def test_untrusted_hypothesis_and_missing_permission_cannot_be_promoted(self):
        v = deepcopy(CASES["missing-server-readback"])
        v["evidence"]["candidate_interpretations"][0]["status"] = "APPROVED_ORACLE"
        with self.assertRaises(AssertionError):
            validate_design_vector(v)
        v = deepcopy(CASES["missing-server-readback"])
        v["evidence"]["missing_observations"][0]["permission_granted"] = True
        with self.assertRaises(AssertionError):
            validate_design_vector(v)


if __name__ == "__main__":
    unittest.main()
