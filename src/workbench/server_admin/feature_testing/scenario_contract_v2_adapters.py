"""Deterministic NONCANONICAL staging/evidence compatibility projections.

These pure functions never emit a runnable scenario, verified identity,
source-authenticated digest, approved oracle or execution permission. Source
citations are copied exactly; normalized v2 candidates are a separate view.
No filesystem access, network, decoding, database read or runner dispatch.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .scenario_contract_v2 import _validate_sources

_CONTRACT = "contract_v2_staging_projection_v1_NONCANONICAL"
_STATES = {"EXACT", "INFERRED", "AMBIGUOUS", "UNRESOLVED", "UNSUPPORTED"}
_KINDS = {"item", "key_item", "npc", "mob", "zone", "catalog"}


def _citations(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("staging citations must be a list")
    if len(value) > 100:
        raise ValueError("staging citations exceed bounded review limit")
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("invalid staged citation")
    return value


def _declared_refs(node: dict) -> list[dict]:
    refs = []
    for key in ("source_refs", "oracle_refs", "oracle_sources"):
        if key in node:
            refs += _citations(node[key])
    return refs


def project_domain_case(staging: dict, case_id: str) -> dict:
    """Project one staged case as *reviewable metadata*, never as a v1 spec.

    Citation keys from gardening, RUN/GEO, Salvage and other R5 drafts are
    explicitly enumerated. Unrecognized source locations are not guessed;
    unknown digests stay null. Raw citation objects and free-text readbacks
    remain available in source order.
    """
    if not isinstance(staging, dict) or not isinstance(staging.get("cases"), list):
        raise ValueError("invalid staged domain envelope")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("invalid staged case ID")
    matching = [c for c in staging["cases"]
                if isinstance(c, dict) and c.get("case_id") == case_id]
    if len(matching) != 1:
        raise ValueError("staging case missing or duplicate")
    case = matching[0]
    if case.get("execution_status") != "design_only" or case.get("runner") not in ("unassigned", None):
        raise ValueError("non-design-only staged case cannot be projected")
    if case.get("execution_authorized") is True or case.get("execution_enabled") is True:
        raise ValueError("staged case claims execution permission")
    steps = case.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("staged steps missing/out of bounds")
    ids = [s.get("id") for s in steps if isinstance(s, dict)]
    if len(ids) != len(steps) or any(not isinstance(v, str) or not v for v in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or duplicate staged step IDs")
    lane = case.get("execution_lane", case.get("lane"))
    if not isinstance(lane, str) or lane not in ("observe-now", "needs-readback", "needs-mutation", "needs-deploy"):
        raise ValueError("unrecognized staging execution lane")
    if "execution_lane" in case and "lane" in case and case["execution_lane"] != case["lane"]:
        raise ValueError("conflicting staging execution lanes")

    original = []
    original += _declared_refs(case)
    oracle = case.get("oracle")
    if oracle is not None:
        if not isinstance(oracle, dict):
            raise ValueError("invalid staged oracle")
        original += _declared_refs(oracle)
    source_map: dict[tuple, str] = {}
    canonical = []
    by_step = []
    def add_citation(citation: dict) -> str:
        mandatory = ("repository", "path", "commit", "line_start", "line_end")
        if any(k not in citation for k in mandatory):
            raise ValueError("incomplete staged source reference")
        unique = tuple(citation[k] for k in mandatory)
        try:
            if unique in source_map:
                return source_map[unique]
        except TypeError as exc:
            raise ValueError("unhashable staged source reference") from exc
        encoded = json.dumps(unique, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        ref = "src_" + sha256(encoded.encode("utf-8")).hexdigest()[:24]
        if any(s["ref"] == ref for s in canonical):
            raise ValueError("staging source-ref collision")
        projected = {
            "ref": ref, "repository": citation["repository"],
            "path": citation["path"], "line_start": citation["line_start"],
            "line_end": citation["line_end"], "revision": citation["commit"],
            "classification": "dsp_source" if citation["repository"] == "sarthax/darkstar-to-valhalla"
                              else "documentation",
            "sha256": None,
        }
        _validate_sources([projected])
        if len(canonical) >= 20:
            raise ValueError("more than 20 distinct v2 sources; human split required")
        canonical.append(projected)
        source_map[unique] = ref
        return ref

    case_refs = [add_citation(c) for c in original]
    for step in steps:
        if step.get("execution_authorized") is True or step.get("manual_execution_allowed") is True:
            raise ValueError("staged step claims execution authorization")
        sr = _declared_refs(step)
        original += sr
        by_step.append({
            "step_id": step["id"],
            "source_refs": [add_citation(c) for c in sr],
            "capability": "unassigned", "operation_class": "unknown",
            "required_permissions": [], "required_readbacks": [],
            "approval_required": True, "execution_gate": "blocked",
        })
    readback = case.get("readback")
    if readback is not None and not isinstance(readback, dict):
        raise ValueError("invalid staged readback specification")
    return {
        "projection_contract": _CONTRACT, "canonical_import_allowed": False,
        "execution_enabled": False, "independent_verification": "NOT_ESTABLISHED",
        "feature_id": case.get("feature_id"), "case_id": case_id,
        "execution_lane": lane, "staged_verdict": case.get("verdict"),
        "source_refs_original": deepcopy(original),
        "case_source_ref_ids": case_refs, "sources": canonical,
        "step_requirements": by_step,
        "readback_proposals_original": deepcopy(readback),
        "oracle_projection": "UNKNOWN_REQUIRES_CANONICAL_ASSERTION_AND_INDEPENDENT_REVIEW",
        "oracles": [], "parameters": [],
        "blocking_gaps": [
            "NO_CANONICAL_V1_ASSERTION_CONVERSION",
            "NO_SOURCE_FILE_SHA256_OR_DEPLOYMENT_ATTESTATION",
            "READBACK_AND_OPERATOR_AUTHORIZATION_UNVERIFIED",
        ],
    }


def project_identity_diagnostic(diagnostic: dict, *, kind: str) -> dict:
    """Map Agent D source-record classes conservatively; do not trust EXACT.

    Source-side row keys, parser details, alternatives and hashes remain in
    the complete original diagnostic rather than being recast as DSP proof.
    """
    if not isinstance(diagnostic, dict) or kind not in _KINDS:
        raise ValueError("invalid evidence identity candidate")
    state = diagnostic.get("classification")
    if state not in _STATES:
        raise ValueError("unsupported evidence classification")
    # An allegedly independently verified capture row does NOT elevate it:
    # source bytes / client + DSP namespace have not been crosschecked here.
    selection = diagnostic.get("identity")
    if selection is not None and not (
        type(selection) is int and 0 <= selection <= 2**32 - 1 or
        isinstance(selection, str) and 0 < len(selection) <= 120 and
        all(c.isalnum() or c in "_:-." for c in selection)
    ):
        raise ValueError("invalid typed candidate identity")
    namespace = diagnostic.get("namespace")
    if namespace is not None and (
        not isinstance(namespace, str) or not namespace or len(namespace) > 64 or
        not namespace[0].isalpha() or
        any(not (c.isalnum() or c in "_-") for c in namespace)
    ):
        raise ValueError("invalid typed candidate namespace")
    zone_id = diagnostic.get("zone_id")
    if zone_id is not None and not (type(zone_id) is int and 0 <= zone_id <= 2**32 - 1):
        raise ValueError("invalid typed candidate zone scope")
    if state in {"AMBIGUOUS", "UNRESOLVED", "UNSUPPORTED"}:
        binding_state, selection = ("ambiguous" if state == "AMBIGUOUS" else "unresolved"), None
    else:
        binding_state = "candidate" if selection is not None else "unresolved"
    return {
        "classification_original": state,
        "binding_state": binding_state,
        "kind": kind, "identity_candidate": selection,
        "namespace_candidate": namespace, "zone_id_candidate": zone_id,
        "source_identity_verified": False,
        "execution_enabled": False,
        "operator_source_review_required": True,
        "source_diagnostic_original": deepcopy(diagnostic),
    }


def project_expected_candidate(candidate: dict | None) -> dict:
    """An Agent D expected-value proposal never becomes a normative oracle."""
    if candidate is not None and not isinstance(candidate, dict):
        raise ValueError("invalid source expectation candidate")
    return {
        "oracle_type": "unknown", "confidence": "unknown", "source_refs": [],
        "normative_expected": None, "approved": False,
        "readiness": ("REJECT_CAPTURE_DERIVED_ORACLE" if candidate and candidate.get("from_capture") is True
                      else "REVIEW_REQUIRED_SOURCE_CANDIDATE" if candidate else "UNKNOWN"),
        "candidate_original": deepcopy(candidate),
        "execution_enabled": False,
    }
