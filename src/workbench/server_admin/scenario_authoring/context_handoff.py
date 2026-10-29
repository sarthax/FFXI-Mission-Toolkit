"""Untrusted coverage/evidence authoring references: offline validation only.

No capture database, URL fetching, specification saving, evidence mutation, or
gameplay operations. An internally matching projection digest is not a trusted
attestation of physical capture bytes or the source index.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
_CHECKSUM = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = "data/testing/feature_test_readiness.json"
_COVERAGE = "coverage_behavior_reference_v1"
_DECISIONS = "offline_capture_review_decisions_v1_NONCANONICAL"
_OBSERVED = "scenario_developer_manual_handoff_v1_DESIGN_ONLY"
_KINDS = {"npc", "npc_name", "zone", "item", "item_name", "key_item",
          "event", "dialog", "message_or_event", "packet"}
_ALLOWED = {"ACCEPT", "EDIT", "REJECT"}
_MAX_STEPS = 100
_MAX_REFS = 4000


def coverage_path(value: str) -> tuple[str, str]:
    """Accept exactly the coverage router's bounded relative context URL."""
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError("Missing, expired or oversized coverage context reference")
    match = re.fullmatch(
        r"/feature-testing/coverage/context/([A-Za-z0-9][A-Za-z0-9_-]{0,119})/"
        r"([A-Za-z0-9][A-Za-z0-9_-]{0,119})", value
    )
    if not match:
        raise ValueError("Unsupported coverage reference; return to the Coverage Matrix")
    return match.groups()


def coverage_context(source: dict, reference: str) -> dict:
    """Fail closed on stale, incompatible or tampered endpoint responses."""
    feature, behavior = coverage_path(reference)
    if not isinstance(source, dict) or source.get("contract") != _COVERAGE:
        raise ValueError("Coverage contract unavailable or incompatible; refresh the Matrix")
    expected = {
        "feature_id": feature,
        "behavior_ref": behavior,
        "reference_kind": "declared_test_case_intent_not_behavior_trace_identity",
        "source": _SOURCE,
        "source_pointer": f"features[id={feature}].cases[id={behavior}]",
        "source_revision": "UNPINNED", "expected_oracle": "UNKNOWN",
        "proposed_case_id": None, "assertions": [], "observations": [],
        "capability_bindings": [], "context_only": True, "design_only": True,
        "review_required": True, "auto_populate_allowed": False,
        "auto_save_allowed": False, "execution_enabled": False,
    }
    if any(source.get(k) != v for k, v in expected.items()):
        raise ValueError("Coverage reference changed or claims unverified authority")
    if not isinstance(source.get("label"), str) or not 1 <= len(source["label"]) <= 240:
        raise ValueError("Coverage source intent missing")
    if not isinstance(source.get("category"), str) or not 1 <= len(source["category"]) <= 40:
        raise ValueError("Coverage category invalid")
    return {
        "contract": _COVERAGE,
        "feature_id": feature, "behavior_ref": behavior,
        "label": source["label"], "category": source["category"],
        "source": _SOURCE, "source_pointer": expected["source_pointer"],
        "source_revision": "UNPINNED", "expected_oracle": "UNKNOWN",
        "context_only": True, "design_only": True, "review_required": True,
        "auto_populate_allowed": False, "auto_save_allowed": False,
        "proposed_case_id": None, "assertions": [], "observations": [],
        "capability_bindings": [], "execution_enabled": False,
        "return_url": "/feature-testing/coverage",
    }


def _text(value: object, label: str, maximum: int = 500) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ValueError(f"Invalid {label} in evidence review")
    return value


def _decision_items(items: object, ids: set[str], key: str) -> dict[str, dict]:
    if not isinstance(items, list) or len(items) > _MAX_REFS:
        raise ValueError("Invalid or unbounded reviewed decisions")
    output: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not set(item).issubset({key, "decision", "note", "edited_title", "edited_value"}):
            raise ValueError("Unrecognized evidence decision fields")
        ref = item.get(key)
        choice = item.get("decision")
        if ref not in ids or ref in output or choice not in _ALLOWED:
            raise ValueError("Unknown or duplicate evidence reviewer identity")
        _text(item.get("note"), "review note")
        edit_key = "edited_title" if key == "step_id" else "edited_value"
        other_key = "edited_value" if key == "step_id" else "edited_title"
        if other_key in item:
            raise ValueError("Mismatched reviewer edit field")
        if choice == "EDIT":
            _text(item.get(edit_key), "edited reviewer text")
        elif edit_key in item:
            raise ValueError("Unexpected edit for non-edit reviewer decision")
        output[ref] = item
    return output


def inspect_evidence_review(payload: dict) -> dict:
    """Check offline handoff *internal* consistency and return suggestions.

    This does not verify source files or authenticate the index. To prove those,
    an independent, trusted capture-index lookup is still required. Never use
    these steps as normative oracles or executable bindings.
    """
    if not isinstance(payload, dict) or set(payload) != {
        "contract", "capture_id", "capture_projection_sha256", "observed_handoff",
        "step_decisions", "binding_decisions", "review_status",
        "normative_expected", "verdict", "execution_enabled", "approved_for_execution",
    } or payload.get("contract") != _DECISIONS:
        raise ValueError("Unsupported or modified offline evidence review file")
    doc = payload.get("observed_handoff")
    expected_doc_keys = {
        "contract", "source_contract", "capture_id", "classification",
        "review_status", "step_review_complete", "binding_review_complete",
        "review_complete", "normative_expected", "verdict",
        "execution_enabled", "approved_for_execution", "capture_projection_sha256",
        "timeline", "proposed_behavior", "reviewed_steps", "evidence_map",
        "canonical_specification_seed", "review_gaps", "continue_in_scenario_developer",
    }
    if not isinstance(doc, dict) or doc.get("contract") != _OBSERVED or set(doc) != expected_doc_keys:
        raise ValueError("Original observed-only handoff missing or incompatible")
    if not (type(payload.get("capture_id")) is int and payload["capture_id"] > 0
            and payload["capture_id"] == doc.get("capture_id")
            and payload.get("review_status") == doc.get("review_status") == "MANUAL_AUTHORING_REQUIRED"
            and payload.get("normative_expected") is doc.get("normative_expected") is None
            and payload.get("verdict") == doc.get("verdict") == "UNKNOWN"
            and payload.get("execution_enabled") is doc.get("execution_enabled") is False
            and payload.get("approved_for_execution") is doc.get("approved_for_execution") is False
            and doc.get("classification") == "OBSERVED_ONLY"
            and doc.get("source_contract") == "evidence_to_scenario_review_v0_NONCANONICAL"):
        raise ValueError("Evidence cannot claim execution, approval or normative outcomes")
    continuation = doc.get("continue_in_scenario_developer")
    if not isinstance(continuation, dict) or any([
        continuation.get("route") != "/scenario-developer",
        continuation.get("automatic_import") is not False,
        continuation.get("not_a_save_payload") is not True,
        continuation.get("no_execution") is not True,
        continuation.get("status") != "MANUAL_HANDOFF_ONLY",
    ]):
        raise ValueError("Unsafe evidence handoff destination or automatic import claim")
    seed = doc.get("canonical_specification_seed")
    if not isinstance(seed, dict) or any([
        seed.get("runner") != "unassigned", seed.get("execution_status") != "design_only",
        seed.get("feature_id") is not None, seed.get("case_id") is not None,
        seed.get("assertions") != [], seed.get("observations") != [],
        not isinstance(seed.get("authoring"), dict),
    ]) or any([
        seed["authoring"].get("review_required") is not True,
        seed["authoring"].get("state") != "reverse_capture_review_required",
        seed["authoring"].get("execution_policy") != "disabled",
        seed["authoring"].get("evidence_provenance") != "unverified_indexed_capture",
    ]):
        raise ValueError("Review seed attempted to promote a draft or fabricate assertions")
    seed_steps = seed.get("steps")
    if not isinstance(seed_steps, list) or any(
        not isinstance(step, dict) or
        not isinstance(step.get("expected"), str) or
        not step["expected"].startswith("UNKNOWN") or
        step.get("assertion_ids") != [] or step.get("evidence_refs") != []
        for step in seed_steps
    ):
        raise ValueError("Captured canonical seed must not contain normative assertions or evidence bindings")
    observations = doc.get("reviewed_steps")
    evidence = doc.get("evidence_map")
    if (not isinstance(observations, list) or not 1 <= len(observations) <= _MAX_STEPS
            or not isinstance(evidence, dict) or len(evidence) > _MAX_REFS):
        raise ValueError("Missing or unbounded indexed evidence projection")
    if not all(isinstance(k, str) and k.startswith("capture-row:") for k in evidence):
        raise ValueError("Invalid evidence reference namespace")
    # Project precisely the checksum inputs emitted by PR #1276.
    projected = []
    steps = []
    bindings: dict[str, dict] = {}
    ids = set()
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("Invalid reviewed evidence step")
        sid = _text(item.get("step_id"), "source step ID", 120)
        if sid in ids or not _REF.fullmatch(sid):
            raise ValueError("Duplicate or invalid evidence step identity")
        ids.add(sid)
        title = _text(item.get("observed_summary"), "source observation summary")
        refs = item.get("evidence_refs")
        bs = item.get("bindings")
        if not isinstance(refs, list) or not refs or len(refs) > 40 or any(r not in evidence for r in refs):
            raise ValueError("Unresolvable step evidence references")
        if not isinstance(bs, list) or len(bs) > 30:
            raise ValueError("Invalid source identity candidates")
        proj_bindings = []
        views = []
        for b in bs:
            if not isinstance(b, dict):
                raise ValueError("Invalid source identity candidate")
            bid = _text(b.get("binding_id"), "candidate ID", 120)
            kind = b.get("kind")
            brefs = b.get("evidence_refs")
            if bid in bindings or kind not in _KINDS or not isinstance(brefs, list) or any(r not in evidence for r in brefs):
                raise ValueError("Duplicate, unsupported or untraceable candidate identity")
            if b.get("authority") != "UNVERIFIED_CAPTURE_IDENTITY":
                raise ValueError("Source identity incorrectly marked verified")
            if b.get("classification") not in {"DECODED", "AMBIGUOUS", "UNSUPPORTED", "INFERRED"}:
                raise ValueError("Unsupported identity classification")
            bindings[bid] = b
            proj_bindings.append({k: b[k] for k in ("binding_id", "observed_value", "evidence_refs")})
            views.append({"binding_id": bid, "kind": kind,
                          "classification": b["classification"],
                          "identity": str(b.get("observed_value"))[:120],
                          "confidence": "UNVERIFIED_CAPTURE_IDENTITY"})
        if item.get("normative_expected") is not None or item.get("verdict") != "UNKNOWN" or item.get("review_required") is not True:
            raise ValueError("Captured result cannot become a normative oracle")
        projected.append({"id": sid, "observed_summary": title, "evidence_refs": refs,
                          "bindings": proj_bindings})
        steps.append({"step_id": sid, "observed_summary": title,
                      "evidence_refs": refs[:], "bindings": views})
    indexed_fingerprints = {}
    for key, value in evidence.items():
        if not isinstance(value, dict) or value.get("ref_id") != key or value.get("capture_id") != payload["capture_id"]:
            raise ValueError("Inconsistent original indexed evidence reference")
        source = value.get("source")
        if not isinstance(source, dict):
            raise ValueError("Original evidence source missing")
        indexed_fingerprints[key] = []
        locations = source.get("references", [])
        if not isinstance(locations, list) or len(locations) > 40:
            raise ValueError("Invalid or unbounded source locators")
        for ref in locations:
            if not isinstance(ref, dict):
                raise ValueError("Invalid source locator")
            digest = ref.get("source_sha256")
            if digest is not None and (not isinstance(digest, str) or not _CHECKSUM.fullmatch(digest)):
                raise ValueError("Malformed source fingerprint")
            manifest = ref.get("source_manifest")
            parser = manifest.get("parser_version") if isinstance(manifest, dict) else None
            indexed_fingerprints[key].append({
                "ref_id": key, "sha256": digest or "UNKNOWN",
                "parser_version": str(parser)[:60] if parser is not None else "UNKNOWN",
                "verification": "INDEXED_SOURCE_METADATA_NOT_REHASHED",
            })
    for step in steps:
        step["source_fingerprints"] = [
            item for key in step["evidence_refs"] for item in indexed_fingerprints[key]
        ][:80]
    checksum = sha256(json.dumps({
        "capture_id": payload["capture_id"], "evidence_map": evidence, "steps": projected,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    if not _CHECKSUM.fullmatch(str(payload.get("capture_projection_sha256"))) or checksum != payload["capture_projection_sha256"] or checksum != doc.get("capture_projection_sha256"):
        raise ValueError("Indexed projection fingerprint mismatch: file is stale or tampered")
    decisions = _decision_items(payload.get("step_decisions"), ids, "step_id")
    reviewed_bindings = _decision_items(payload.get("binding_decisions"), set(bindings), "binding_id")
    for step in steps:
        d = decisions.get(step["step_id"])
        step["decision"] = d["decision"] if d else "PENDING"
        step["review_note"] = d["note"] if d else None
        step["suggested_title"] = (d["edited_title"] if d and d["decision"] == "EDIT"
                                   else step["observed_summary"])
        for b in step["bindings"]:
            reviewed = reviewed_bindings.get(b["binding_id"])
            b["review_decision"] = reviewed["decision"] if reviewed else "PENDING"
            # Reviewer edits are proposed candidates, never revised source values.
            b["suggested_identity"] = (
                str(reviewed["edited_value"])[:120]
                if reviewed and reviewed["decision"] == "EDIT"
                else b["identity"]
            )
    return {
        "contract": "editor_evidence_suggestions_v1",
        "capture_id": payload["capture_id"], "projection_sha256": checksum,
        "projection_matches_embedded_evidence": True,
        "original_capture_authenticated": False,
        "original_source_url": None,
        "source_fingerprints_status": "INDEXED_METADATA_ONLY_NOT_INDEPENDENTLY_REHASHED",
        "review_complete_in_file": (len(decisions) == len(steps) and len(reviewed_bindings) == len(bindings)),
        "steps": steps, "unresolved_bindings": sum(
            b["review_decision"] != "REJECT" for s in steps for b in s["bindings"]
        ),
        "required_confirmation": True, "execution_enabled": False,
        "normative_expected": "UNKNOWN",
        "return_instructions": "Return to the original offline Evidence Reviewer artifact; its path is not present in the bundle.",
    }
