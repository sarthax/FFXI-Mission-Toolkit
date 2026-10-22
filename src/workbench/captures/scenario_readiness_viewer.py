"""#1313: paired offline capture review/readiness display, never an importer.

All inputs are operator-selected *untrusted local JSON documents*. Recomputed
projection checks establish internal pairing, not signature verification of
physical capture files, parser executables, client or DSP state.

This pure adapter has no routes, file IO, DB, runtime, or canonical spec output.
Agent B owns the eventual optional editor UI attachment after #1307 integration.
"""
from __future__ import annotations

from copy import deepcopy
import json

from .scenario_identity_readiness import _observation_digest
from .scenario_readiness_summary import summarize_capture_readiness
from .scenario_review_workflow import _check
from .scenario_handoff import _digest
from workbench.server_admin.scenario_authoring.context_handoff import inspect_evidence_review

_REVIEW = "offline_capture_review_decisions_v1_NONCANONICAL"
_SIDECAR = "capture_reviewer_readiness_sidecar_v0_NONCANONICAL"
_VIEW = "read_only_paired_capture_readiness_view_v1_NONCANONICAL"
_MAX_BYTES = 4_500_000
_SIDECAR_KEYS = {
    "contract", "capture_id", "indexed_observation_projection_sha256",
    "original_handoff_projection_sha256", "original_evidence_handoff",
    "review_decisions", "readiness_diagnostics", "scenario_developer_handoff",
    "normative_expected", "verdict", "automatic_import",
    "approved_for_execution", "execution_enabled",
}


def _limited_document(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(name + " must be a selected JSON object")
    try:
        length = len(json.dumps(value, ensure_ascii=True, separators=(",", ":")))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(name + " is not serializable JSON") from exc
    if length > _MAX_BYTES:
        raise ValueError(name + " exceeds the bounded offline inspection size")
    return value


def _source_draft(original: dict) -> dict:
    """Rebuild the original indexed observation scope, NOT a canonical spec."""
    source = {
        "contract": "evidence_to_scenario_review_v0_NONCANONICAL",
        "capture_id": original["capture_id"],
        "scenario_status": "DRAFT_REVIEW_REQUIRED",
        "observation_verdict": "UNKNOWN",
        "normative_expected": None,
        "execution_enabled": False, "approved_for_execution": False,
        "steps": deepcopy(original["reviewed_steps"]),
        "evidence_map": deepcopy(original["evidence_map"]),
        "canonical_specification_seed": deepcopy(original["canonical_specification_seed"]),
    }
    _check(source)
    return source


def inspect_paired_readiness(review: dict, sidecar: dict) -> dict:
    """Recompute BOTH source-scoped checksums and produce display-only fields.

    A dishonest actor can re-author a self-consistent pair. The output
    explicitly makes no physical-source authenticity claim.
    """
    review = _limited_document(review, "original reviewed capture")
    sidecar = _limited_document(sidecar, "readiness advisory")
    if review.get("contract") != _REVIEW:
        raise ValueError("Select the original reviewed-decision JSON separately")
    if set(sidecar) != _SIDECAR_KEYS or sidecar.get("contract") != _SIDECAR:
        raise ValueError("Unsupported noncanonical readiness sidecar")
    for doc in (review, sidecar):
        if (doc.get("normative_expected") is not None
                or doc.get("verdict") != "UNKNOWN"
                or doc.get("execution_enabled") is not False
                or doc.get("approved_for_execution") is not False):
            raise ValueError("review/sidecar attempted to claim gameplay approval")
    if sidecar["automatic_import"] is not False:
        raise ValueError("Readiness sidecar cannot request automatic import")
    # Existing standalone reviewed-decision inspector checks the exact review
    # envelope, original step/binding decision rules, source refs and the
    # original_handoff_projection checksum against the embedded original rows.
    inspected = inspect_evidence_review(review)
    original = review["observed_handoff"]
    if (type(review["capture_id"]) is not int
            or sidecar["capture_id"] != review["capture_id"]
            or sidecar["original_evidence_handoff"] != original
            or sidecar["original_handoff_projection_sha256"] != inspected["projection_sha256"]):
        raise ValueError("Original review capture/projection does not match readiness sidecar")
    decisions = sidecar.get("review_decisions")
    if (not isinstance(decisions, dict) or set(decisions) != {"steps", "bindings"}
            or decisions["steps"] != review["step_decisions"]
            or decisions["bindings"] != review["binding_decisions"]):
        raise ValueError("Original reviewer decisions differ across selected files")
    draft = _source_draft(original)
    index_sha = _observation_digest(draft)
    if sidecar["indexed_observation_projection_sha256"] != index_sha:
        raise ValueError("Indexed capture projection digest mismatch")
    # Compare the *entire producer output*, not selectively trusted flags.
    # This rejects invented source-file fingerprints, source row identities,
    # modified review decisions, physical source claims and fake approvals.
    expected = summarize_capture_readiness(draft)
    if (sidecar["readiness_diagnostics"] != expected
            or sidecar["scenario_developer_handoff"] != expected["scenario_developer_handoff"]):
        raise ValueError("Readiness projection has changed or contains unverified context")
    projection = expected["scenario_developer_handoff"]["read_only_projection"]
    if projection["indexed_capture_projection_sha256"] != index_sha:
        raise ValueError("Source projection integrity mismatch")
    if not isinstance(projection["steps"], list) or not projection["steps"]:
        raise ValueError("No supported indexed evidence observations")
    if (projection["physical_source_authenticated"] is not False
            or projection["automatic_import"] is not False
            or projection["save_allowed"] is not False
            or projection["approved_for_execution"] is not False
            or projection["execution_enabled"] is not False):
        raise ValueError("Readiness producer cannot grant source/execution trust")
    output_steps = []
    for row in projection["steps"]:
        if (row["canonical_step_id"] is not None
                or row["canonical_source_association"] != {
                    "state": "UNASSIGNED_REQUIRES_INDEPENDENT_CANONICAL_CROSSWALK",
                    "scope": None, "source_refs": []}
                or row["oracle_approval_state"] != "UNAPPROVED"
                or row["normative_expected"] is not None
                or row["verdict"] != "UNKNOWN"
                or row["execution_enabled"] is not False
                or row["readiness_state"] not in {"UNKNOWN", "BLOCKED"}):
            raise ValueError("Observed evidence was promoted into canonical authority")
        for gap in row["missing_readbacks"]:
            if (gap["status"] != "NOT_INDEPENDENTLY_OBSERVED"
                    or gap["permission_granted"] is not False
                    or gap["capability_registered"] is not False):
                raise ValueError("Missing readback was elevated to a verified capability")
        output_steps.append(deepcopy(row))
    return {
        "contract": _VIEW,
        "capture_id": review["capture_id"],
        "pair_integrity": "BOTH_INDEXED_PROJECTIONS_RECOMPUTED_FROM_SELECTED_REVIEW",
        "original_handoff_projection_sha256": inspected["projection_sha256"],
        "indexed_observation_projection_sha256": index_sha,
        "original_capture_authenticated": False,
        "parser_decoder_authenticated": False,
        "source_bytes_rehashed": False,
        "source_integrity": deepcopy(expected["source_integrity"]),
        "source_compatibility_state": projection["source_compatibility_state"],
        "source_provenance_issues": deepcopy(projection["source_provenance_issues"]),
        "steps": output_steps,
        "canonical_step_associations": "UNASSIGNED",
        "scenario_specification": None,
        "review_required": True,
        "automatic_import": False,
        "save_allowed": False,
        "normative_expected": None, "verdict": "UNKNOWN",
        "approved_for_execution": False, "execution_enabled": False,
        "security_notice": (
            "Both hashes validate matching indexed JSON projections only. "
            "No physical capture bytes, parser/decoder, client/DSP source, "
            "independent readback or gameplay outcome were authenticated."),
    }
