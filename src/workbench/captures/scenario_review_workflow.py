"""Offline human review of source-local capture drafts; no database or client writes.

This is an authoring *handoff*, not the published scenario specification,
execution control, an authenticated artifact, or a packet decoder. Reviewer
edits never overwrite capture observations or their source locators.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .scenario_handoff import apply_binding_decisions, _DECISIONS

_CONTRACT = "evidence_to_scenario_review_v0_NONCANONICAL"
_REVIEW = "capture_scenario_reviewer_v1_NONCANONICAL"
_EXPORT = "scenario_developer_manual_handoff_v1_DESIGN_ONLY"
_UNKNOWN = "UNKNOWN"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _check(draft: dict) -> None:
    """Fail closed on obvious execution, expected-outcome, or schema promotion."""
    if not isinstance(draft, dict) or draft.get("contract") != _CONTRACT:
        raise ValueError("unsupported capture handoff")
    if (draft.get("scenario_status") != "DRAFT_REVIEW_REQUIRED"
            or draft.get("observation_verdict") != _UNKNOWN
            or draft.get("normative_expected") is not None
            or draft.get("execution_enabled") is not False
            or draft.get("approved_for_execution") is not False
            or not isinstance(draft.get("steps"), list)
            or not isinstance(draft.get("evidence_map"), dict)
            or len(draft["steps"]) > 100):
        raise ValueError("unsafe or malformed capture handoff")
    seed = draft.get("canonical_specification_seed")
    if (not isinstance(seed, dict) or seed.get("runner") != "unassigned"
            or seed.get("execution_status") != "design_only"
            or seed.get("feature_id") is not None or seed.get("case_id") is not None
            or seed.get("assertions") != [] or seed.get("observations") != []
            or not isinstance(seed.get("authoring"), dict)
            or seed["authoring"].get("review_required") is not True
            or seed["authoring"].get("state") != "reverse_capture_review_required"
            or seed["authoring"].get("execution_policy") != "disabled"
            or seed["authoring"].get("evidence_provenance") != "unverified_indexed_capture"
            or not isinstance(seed.get("steps"), list)
            or any(not isinstance(s, dict)
                   or not str(s.get("expected", "")).startswith("UNKNOWN")
                   or s.get("assertion_ids") != []
                   or s.get("evidence_refs") != []
                   for s in seed["steps"])):
        raise ValueError("canonical seed must remain incomplete and design-only")
    for step in draft["steps"]:
        if (not isinstance(step, dict) or step.get("normative_expected") is not None
                or step.get("verdict") != _UNKNOWN or step.get("review_required") is not True
                or not isinstance(step.get("bindings"), list)
                or not isinstance(step.get("evidence_refs"), list)):
            raise ValueError("unsafe draft step")
        for ref in step["evidence_refs"]:
            if ref not in draft["evidence_map"]:
                raise ValueError("unresolvable evidence reference")


def apply_step_decisions(draft: dict, decisions: list[dict]) -> dict:
    """Review step descriptions, never mutate observed summary or evidence."""
    _check(draft)
    if not isinstance(decisions, list) or len(decisions) > 100:
        raise ValueError("invalid step decisions")
    copy = deepcopy(draft)
    steps = {s["step_id"]: s for s in copy["steps"]}
    if len(steps) != len(copy["steps"]):
        raise ValueError("duplicate step identity")
    seen = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) - {"step_id", "decision", "edited_title", "note"}:
            raise ValueError("unexpected step review keys")
        ident, decision, note = item.get("step_id"), item.get("decision"), item.get("note")
        if ident not in steps or ident in seen or decision not in _DECISIONS:
            raise ValueError("unknown or duplicate step decision")
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500:
            raise ValueError("review note required")
        edited = item.get("edited_title")
        if decision == "EDIT":
            if not isinstance(edited, str) or not 1 <= len(edited.strip()) <= 500:
                raise ValueError("edited step title required")
        elif "edited_title" in item:
            raise ValueError("only EDIT may provide an edited step title")
        steps[ident]["review"] = {
            "decision": decision,
            "edited_title": edited.strip() if decision == "EDIT" else None,
            "note": note.strip(),
        }
        seen.add(ident)
    copy["step_review_complete"] = bool(steps) and all(
        s.get("review", {}).get("decision") in _DECISIONS for s in steps.values()
    )
    _check(copy)
    return copy


def _zone(step: dict):
    return step.get("zone_db")


def _find(step: dict, kind: str):
    found = [b.get("observed_value") for b in step.get("bindings", [])
             if b.get("kind") == kind and b.get("observed_value") is not None]
    return found[0] if len(found) == 1 else None


def _same_literal(a, b) -> bool:
    return a is not None and b is not None and type(a) == type(b) and a == b


def timeline(draft: dict) -> dict:
    """Source-local timeline and *noncausal* candidate groupings.

    No cross-stream sorting, no promotion of identical numbers across
    namespaces, and no claim that one observation caused another.
    """
    _check(draft)
    lanes: dict[tuple, dict] = {}
    steps = draft["steps"]
    for ordinal, step in enumerate(steps, 1):
        lane_key = (step["lane"], str(_zone(step)))
        if lane_key not in lanes:
            lanes[lane_key] = {
                "table": step["lane"], "zone_label": _zone(step),
                "order_basis": step["order_basis"],
                "clock_status": "NOT_ALIGNED_WITH_OTHER_STREAMS",
                "events": [],
            }
        evidence = [draft["evidence_map"][ref] for ref in step["evidence_refs"]]
        sources = []
        for row in evidence:
            source = row["source"]
            sources.append({
                "ref_id": row["ref_id"], "row_key": deepcopy(row["row_key"]),
                "source_status": source.get("status", "UNRESOLVED"),
                "references": deepcopy(source.get("references", [])),
                "time_basis": row.get("time_basis"),
                "native_timestamp": row.get("native_timestamp"),
                "record_class": row.get("record_class"),
                "recorded_metadata": deepcopy(row.get("recorded_metadata", {})),
            })
        lanes[lane_key]["events"].append({
            "step_id": step["step_id"], "lane_ordinal": len(lanes[lane_key]["events"]) + 1,
            "display_ordinal": ordinal, "summary": step["observed_summary"],
            "interpretation": step["interpretation"], "relationship": deepcopy(step["relationship"]),
            "record_class": step["record_class"], "gaps": deepcopy(step["review_gaps"]),
            "evidence_refs": list(step["evidence_refs"]), "sources": sources,
            "bindings": deepcopy(step["bindings"]), "review": deepcopy(step.get("review", {"decision": "PENDING"})),
        })
    associations = []
    for pos, left in enumerate(steps):
        for right in steps[pos + 1:]:
            if left["lane"] == right["lane"]:
                continue
            if not _same_literal(_zone(left), _zone(right)):
                continue
            # Entity-ID matches are only *candidates*: different parsers may
            # use distinct identity namespaces even within the same capture.
            a, b = _find(left, "npc"), _find(right, "npc")
            if _same_literal(a, b) and not isinstance(a, (list, dict)):
                reason = "MATCHING_CAPTURE_ENTITY_FIELD_AND_EXACT_ZONE_LABEL"
            else:
                reason = "MATCHING_ZONE_LABEL_ONLY"
            associations.append({
                "left_step_id": left["step_id"], "right_step_id": right["step_id"],
                "classification": "INFERRED", "basis": reason,
                "causality": "UNPROVEN", "identity": "UNVERIFIED_CROSS_SOURCE",
                "evidence_refs": sorted(set(left["evidence_refs"] + right["evidence_refs"])),
            })
    return {
        "ordering": "PER_SOURCE_LANE_ONLY",
        "cross_stream_clock_alignment": "UNPROVEN",
        "lanes": list(lanes.values()),
        "candidate_associations": associations,
        "warning": "Links are reviewer candidates, not verified NPC ownership, temporal order or gameplay effects",
    }


def behavior_preview(draft: dict) -> dict:
    """Readable proposed BDD is explicitly observation-grounded, not an oracle."""
    _check(draft)
    summarized = [s["observed_summary"] for s in draft["steps"][:12]]
    return {
        "classification": "PROPOSED_OBSERVATION_NARRATIVE",
        "given": [
            "An indexed capture exists with source-local observations; source completeness and authority are unverified",
        ],
        "when": summarized or ["No supported event rows were reconstructed"],
        "then": [
            "UNKNOWN: captured outcomes are not authoritative expected behavior",
            "Independent DSP source citations, preconditions and readback assertions must be authored by a reviewer",
        ],
        "normative_expected": None,
        "verdict": "UNKNOWN",
        "review_required": True,
    }


def manual_editor_handoff(draft: dict) -> dict:
    """Export a design-only review bundle, *not* a validatable/savable spec."""
    _check(draft)
    reviewed = deepcopy(draft)
    steps = reviewed["steps"]
    bindings = [b for s in steps for b in s["bindings"]]
    step_review_complete = bool(steps) and all(
        s.get("review", {}).get("decision") in _DECISIONS for s in steps
    )
    binding_review_complete = bool(bindings) and all(
        b.get("review", {}).get("decision") in _DECISIONS for b in bindings
    )
    source_refs = reviewed["evidence_map"]
    # A tooling checksum of the indexed observation projection, NOT an
    # authentication claim about the original physical raw capture bytes.
    checksum = sha256(_canonical({
        "capture_id": reviewed["capture_id"],
        "evidence_map": source_refs,
        "steps": [{
            "id": s["step_id"], "observed_summary": s["observed_summary"],
            "evidence_refs": s["evidence_refs"],
            "bindings": [{k: b[k] for k in ("binding_id", "observed_value", "evidence_refs")}
                         for b in s["bindings"]],
        } for s in steps],
    }).encode("utf-8")).hexdigest()
    return {
        "contract": _EXPORT, "source_contract": _CONTRACT,
        "capture_id": reviewed["capture_id"], "classification": "OBSERVED_ONLY",
        "review_status": "MANUAL_AUTHORING_REQUIRED",
        "step_review_complete": step_review_complete,
        "binding_review_complete": binding_review_complete,
        "review_complete": step_review_complete and binding_review_complete,
        "normative_expected": None, "verdict": "UNKNOWN",
        "execution_enabled": False, "approved_for_execution": False,
        "capture_projection_sha256": checksum,
        "timeline": timeline(reviewed), "proposed_behavior": behavior_preview(reviewed),
        "reviewed_steps": steps,
        "evidence_map": source_refs,
        "canonical_specification_seed": deepcopy(reviewed["canonical_specification_seed"]),
        "review_gaps": deepcopy(reviewed["review_gaps"]),
        "continue_in_scenario_developer": {
            "destination": "Scenario Developer (#1261)", "route": "/scenario-developer",
            "status": "MANUAL_HANDOFF_ONLY", "automatic_import": False,
            "payload_kind": "UNTRUSTED_OBSERVED_GUIDANCE",
            "steps": [
                "Open Scenario Developer manually; start a new design-only specification",
                "Review proposed Given/When/Then, identities and observed steps against original evidence",
                "Supply authorized feature/case IDs, independent DSP file:line+commit oracles, preconditions, cleanup, observations and assertions",
                "Validate through accepted canonical schema; do not copy missing oracles from captured outcomes",
            ],
            "not_a_save_payload": True,
            "no_execution": True,
        },
    }


def replay_offline_review(draft: dict, payload: dict) -> dict:
    """Validate a downloaded offline decision file against original indexed input.

    An exported bundle is untrusted. Only explicit reviewer decisions are
    replayed; no observed source, identity, or canonical schema fields are
    accepted from the browser as replacements.
    """
    original = manual_editor_handoff(draft)
    if (not isinstance(payload, dict)
            or set(payload) != {
                "contract", "capture_id", "capture_projection_sha256",
                "observed_handoff", "step_decisions", "binding_decisions",
                "review_status", "normative_expected", "verdict",
                "execution_enabled", "approved_for_execution",
            }
            or payload["contract"] != "offline_capture_review_decisions_v1_NONCANONICAL"
            or payload["capture_id"] != original["capture_id"]
            or payload["capture_projection_sha256"] != original["capture_projection_sha256"]
            or payload["observed_handoff"] != original
            or payload["review_status"] != "MANUAL_AUTHORING_REQUIRED"
            or payload["normative_expected"] is not None
            or payload["verdict"] != "UNKNOWN"
            or payload["execution_enabled"] is not False
            or payload["approved_for_execution"] is not False):
        raise ValueError("invalid or modified offline review bundle")
    candidate = apply_binding_decisions(draft, payload["binding_decisions"])
    candidate = apply_step_decisions(candidate, payload["step_decisions"])
    reviewed = manual_editor_handoff(candidate)
    if reviewed["capture_projection_sha256"] != original["capture_projection_sha256"]:
        raise ValueError("indexed source projection changed during review")
    return reviewed
