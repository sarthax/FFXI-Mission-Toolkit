"""Read-only, reviewer-facing evidence readiness with advisory contract_v2 mapping.

This adapter wraps the indexed capture identity diagnostic, never changes a
canonical specification, never grants SOURCE VERIFIED/approval, and cannot run.
Agent C owns contract_v2; mapping here is strictly non-importable guidance.
"""
from __future__ import annotations

from copy import deepcopy
import re

from .scenario_identity_readiness import assess_evidence_readiness, _observation_digest
from .scenario_review_workflow import _check

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
_ALLOWED_PARAM_KINDS = {"npc": "npc", "item": "item", "key_item": "key_item",
                        "zone": "zone", "npc_name": "npc", "item_name": "item"}
_OBSERVATIONS = {
    # name, suggested read-only capability, human diagnostic, necessity
    "capture_events": (
        ("client_dialog", "client_dialog_readback", "Confirm the recorded dialog/event independently from the client", "REQUIRED_CANDIDATE"),
        ("server_event_state", "server_event_state_readback", "Read the NPC event handler branch and persisted state independently", "REQUIRED_CANDIDATE"),
        ("npc_state", "server_npc_state_readback", "Check authoritative NPC existence, phase, despawn and interaction state", "CONDITIONAL"),
        ("mob_state", "server_mob_state_readback", "Check authoritative mob claim, target, HP and despawn when the event involves a mob", "CONDITIONAL"),
        ("job_state", "server_job_state_readback", "Check server job/subjob/level and ability prerequisites when the event depends on job state", "CONDITIONAL"),
        ("quest_variables", "server_quest_variable_readback", "Read quest or mission variables before and after a relevant handler branch", "CONDITIONAL"),
        ("instance_state", "server_instance_state_readback", "Inspect instance identity, owner, phase and timer when relevant", "CONDITIONAL"),
        ("temporary_items", "client_temporary_item_readback", "Inspect temporary-item state when an event depends on a battlefield or instance item", "CONDITIONAL"),
    ),
    "capture_eventview": (
        ("client_dialog", "client_dialog_readback", "Reconcile EventView MesNum against the local typed client event/dialog index", "REQUIRED_CANDIDATE"),
        ("server_event_state", "server_event_state_readback", "Observe the authoritative event/CSID handler result", "REQUIRED_CANDIDATE"),
        ("job_state", "server_job_state_readback", "Read authoritative main/subjob and job prerequisite state if the handler uses it", "CONDITIONAL"),
        ("quest_variables", "server_quest_variable_readback", "Read quest/mission variables when referenced by the scripted branch", "CONDITIONAL"),
        ("instance_state", "server_instance_state_readback", "Read instance phase when the captured event was instanced", "CONDITIONAL"),
        ("temporary_items", "client_temporary_item_readback", "Read temporary-item state if the scripted event uses it", "CONDITIONAL"),
    ),
    "capture_ki_events": (
        ("client_key_items", "client_key_item_readback", "Read the actual held key-item list in the client", "REQUIRED_CANDIDATE"),
        ("server_key_items", "server_key_item_readback", "Read the persisted server key-item state independently", "REQUIRED_CANDIDATE"),
        ("quest_variables", "server_quest_variable_readback", "Read associated quest variables if key-item grants depend on a branch", "CONDITIONAL"),
    ),
    "capture_structured_records": (
        ("client_inventory", "client_inventory_readback", "Read actual bag and quantity in the client", "REQUIRED_CANDIDATE"),
        ("server_inventory", "server_inventory_readback", "Read authoritative persisted server bag and quantity", "REQUIRED_CANDIDATE"),
        ("client_equipment", "client_equipment_readback", "Inspect equipped slot and equipment storage when the item is gear", "CONDITIONAL"),
        ("server_furnishings", "server_furnishing_readback", "Inspect furnishings/installed layout when the item is furniture", "CONDITIONAL"),
        ("temporary_items", "client_temporary_item_readback", "Inspect temporary-item inventory when the recorded item is instance-scoped", "CONDITIONAL"),
    ),
    "capture_raw_packets": (
        ("packet_decoder", "decoder_revision_readback", "Attest decoder version and exact decoded field coverage", "REQUIRED_CANDIDATE"),
        ("server_receipt", "server_receipt_readback", "Obtain independent authoritative server receipt and resulting state", "REQUIRED_CANDIDATE"),
    ),
}

def _integrity(draft: dict, expected_projection: str | None,
               expected_dsp_commit: str | None, steps: list[dict]) -> dict:
    sha = _observation_digest(draft)
    if expected_projection is not None and (
            not isinstance(expected_projection, str) or not _SHA256.fullmatch(expected_projection)):
        raise ValueError("invalid pinned indexed-projection SHA-256")
    if expected_dsp_commit is not None and (
            not isinstance(expected_dsp_commit, str) or not _SHA40.fullmatch(expected_dsp_commit)):
        raise ValueError("invalid expected DSP source revision")
    problems = []
    if expected_projection and sha.lower() != expected_projection.lower():
        problems.append({"code": "CAPTURE_PROJECTION_CHANGED", "severity": "BLOCKED",
                         "reason": "Indexed evidence differs from the independently pinned prior projection"})
    if not expected_projection:
        problems.append({"code": "CAPTURE_PROJECTION_NOT_PINNED", "severity": "UNKNOWN",
                         "reason": "No independently retained projection fingerprint was supplied"})
    for ref, row in draft["evidence_map"].items():
        if not isinstance(row, dict) or row.get("ref_id") != ref:
            raise ValueError("evidence reference identity mismatch")
        source = row.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("references"), list):
            raise ValueError("indexed source locator metadata invalid")
        if source.get("status") not in {"LOCATED_SOURCE_SPAN", "FILE_LEVEL_ONLY"}:
            problems.append({"code": "SOURCE_LOCATOR_UNRESOLVED", "severity": "UNKNOWN",
                             "ref_id": ref, "reason": "Missing/ambiguous/nonmatching indexed source locator"})
        if not source["references"]:
            continue
        for locator in source["references"]:
            if not isinstance(locator, dict):
                raise ValueError("malformed source locator")
            claimed = locator.get("source_sha256")
            manifest = locator.get("source_manifest")
            if (not isinstance(manifest, dict)
                    or not manifest.get("parser_name")
                    or not manifest.get("parser_version")):
                problems.append({"code": "PARSER_REVISION_UNPINNED", "severity": "UNKNOWN",
                                 "ref_id": ref, "reason": "Parser name/version or recognized manifest missing"})
            elif manifest.get("ingest_status") != "RECOGNIZED":
                problems.append({"code": "PARSER_OR_CAPTURE_INGEST_UNRECOGNIZED",
                                 "severity": "UNKNOWN", "ref_id": ref,
                                 "reason": "Parser/version/capture ingest is not recognized by the indexed source manifest; no semantic decoder attestation"})
            if not isinstance(claimed, str) or not _SHA256.fullmatch(claimed):
                problems.append({"code": "SOURCE_DIGEST_UNPINNED", "severity": "UNKNOWN",
                                 "ref_id": ref, "reason": "No well-formed indexed source digest"})
            elif not isinstance(manifest, dict):
                problems.append({"code": "SOURCE_MANIFEST_UNAVAILABLE", "severity": "UNKNOWN",
                                 "ref_id": ref, "reason": "No source manifest to compare with indexed locator digest"})
            elif not isinstance(manifest.get("sha256"), str) or not _SHA256.fullmatch(manifest["sha256"]):
                problems.append({"code": "SOURCE_MANIFEST_DIGEST_UNPINNED", "severity": "UNKNOWN",
                                 "ref_id": ref, "reason": "Manifest lacks a well-formed source digest; no digest conflict proven"})
            elif manifest["sha256"].lower() != claimed.lower():
                problems.append({"code": "SOURCE_MANIFEST_DIGEST_MISMATCH", "severity": "BLOCKED",
                                 "ref_id": ref, "reason": "Indexed locator and recorded source manifest disagree"})
    for entry in steps:
        oracle = entry["oracle"]
        pinned = oracle.get("independent_source")
        if expected_dsp_commit and pinned and pinned.get("dsp_commit", "").lower() != expected_dsp_commit.lower():
            problems.append({"code": "DSP_REVISION_INCOMPATIBLE", "severity": "BLOCKED",
                             "step_id": entry["step_id"], "reason": "Source oracle revision differs from expected DSP checkout"})
        for blocker in oracle["blockers"]:
            if blocker == "DSP_SOURCE_REVISION_MISMATCH":
                problems.append({"code": "DSP_CATALOG_ORACLE_REVISION_MISMATCH",
                                 "severity": "BLOCKED", "step_id": entry["step_id"],
                                 "reason": "DSP source oracle and catalog snapshot revisions differ"})
    blocked = any(p["severity"] == "BLOCKED" for p in problems)
    return {"state": "BLOCKED" if blocked else "UNKNOWN",
            "indexed_projection_sha256": sha,
            "independent_capture_bytes_authenticated": False,
            "issues": problems,
            "execution_enabled": False}


def _observations(step: dict) -> list[dict]:
    """Describe *missing* independent evidence, not observed facts or active grants.

    The source evidence ref is an investigation pointer, not proof that a
    capability exists or a readback already occurred.
    """
    refs = deepcopy(step["evidence_refs"])
    return [
        {
            "observation": name, "expected_observation_type": name,
            "importance": importance, "status": "NOT_INDEPENDENTLY_OBSERVED",
            "reason_for_gap": (
                "Indexed capture observations do not establish the independent "
                + name.replace("_", " ") + " result; this is a conditional check"
                if importance == "CONDITIONAL" else
                "Indexed capture observations do not establish an independent "
                + name.replace("_", " ") + " result"
            ),
            "evidence_refs": deepcopy(refs),
            "suggested_read_only_capability": capability,
            "how_to_obtain": hint, "review_required": True,
            "capability_registered": False, "permission_granted": False,
        }
        for name, capability, hint, importance in _OBSERVATIONS.get(step["lane"], ())
    ]


def _v2_hints(draft: dict, checked: dict, readbacks_by_step: dict) -> dict:
    """Map to Agent C's *proposed* field names, never publish as contract_v2.

    No schema revision, source trust, permission, ID, assertion or normative
    oracle is invented. Proposal must be re-evaluated after Agent C acceptance.
    """
    params = []
    omitted = []
    for step in checked["steps"]:
        for idx, bind in enumerate(step["identity_candidates"], 1):
            kind = _ALLOWED_PARAM_KINDS.get(bind["kind"])
            if kind is None:
                omitted.append({"step_id": step["step_id"], "kind": bind["kind"],
                                "reason": "No typed parameter kind in proposed contract_v2"})
                continue
            if len(params) >= 30:
                omitted.append({"step_id": step["step_id"], "kind": bind["kind"],
                                "reason": "Proposed v2 parameter limit is 30"})
                continue
            raw = bind["observed_value"]
            identity = raw if (type(raw) is int and 0 <= raw <= 2**32 - 1) else None
            classification = bind["classification"]
            state = "ambiguous" if classification == "AMBIGUOUS" else (
                "candidate" if classification in {"EXACT", "INFERRED"} and identity is not None
                else "unresolved")
            if state != "candidate":
                identity = None
            name = ("obs_" + step["step_id"].replace("-", "_") +
                    "_" + str(idx) + "_" + kind)[:64]
            params.append({
                "name": name, "kind": kind, "identity": identity,
                "namespace": None, "zone_id": None, "binding_state": state,
                "source_refs": [],
            })
    requirements = [{
        "step_id": step["step_id"],
        "capability": "unassigned",
        "operation_class": "unknown",
        "required_permissions": [],
        "required_readbacks": readbacks_by_step[step["step_id"]],
        "approval_required": True,
        "execution_gate": "blocked",
    } for step in checked["steps"]]
    # Sources need a verified repository path and source reference identity,
    # and oracles need assertion IDs on a *valid* canonical v1 spec.
    hints = {"contract_version": 2, "sources": [], "parameters": params,
             "oracles": [], "step_requirements": requirements,
             "fingerprints": {"base_spec_sha256": None, "dsp_commit": None,
                              "headless_commit": None, "toolkit_commit": None}}
    return {
        "status": "ADVISORY_UNACCEPTED_NOT_CANONICAL",
        "target": "Agent C #1285 proposed contract_v2 fields",
        "metadata_shape_preview": hints,
        "omitted_bindings": omitted,
        "blocking_requirements": [
            "Contract #1285 not yet accepted or adopted",
            "Canonical v1 feature/case IDs, observations/assertions and step mappings missing",
            "Physical source revision/namespace reconciliation not independently attested",
            "No reviewer-approved independent gameplay oracle or permitted execution",
        ],
        "automatic_import": False, "execution_enabled": False,
    }



def _indexed_provenance(evidence_map: dict, refs: list[str], issues: list[dict]) -> list[dict]:
    """Only indexed locator/manifest *claims*, no file rehash or decoder proof.

    Keep physical capture file identity separate from its parsed row. An
    ingest parser version is NOT an independently established packet decoder.
    No raw payload is copied into this authoring-facing projection.
    """
    output = []
    for ref in refs:
        original = evidence_map[ref]
        source = original["source"]
        locators = []
        for candidate in source["references"]:
            manifest = candidate.get("source_manifest")
            manifest = manifest if isinstance(manifest, dict) else {}
            locators.append({
                "source_filename": candidate.get("filename"),
                "locator_basis": candidate.get("locator_basis"),
                "source_span": {
                    "start_line": candidate.get("start_line"),
                    "end_line": candidate.get("end_line"),
                    "start_offset": candidate.get("start_offset"),
                    "end_offset": candidate.get("end_offset"),
                },
                "locator_sha256_claim": candidate.get("source_sha256"),
                "manifest_sha256_claim": manifest.get("sha256"),
                "parser_name_claim": manifest.get("parser_name"),
                "parser_version_claim": manifest.get("parser_version"),
                "ingest_status_claim": manifest.get("ingest_status"),
                "parser_support": (
                    "INDEXED_RECOGNIZED_NOT_INDEPENDENTLY_VALIDATED"
                    if manifest.get("ingest_status") == "RECOGNIZED"
                    else "UNRECOGNIZED_OR_UNSUPPORTED"
                ),
                "decoder_version": None,
                "decoder_version_status": "NOT_INDEPENDENTLY_ATTESTED",
                "indexed_digests_rehashed": False,
            })
        output.append({
            "evidence_ref": ref,
            "capture_id": original["capture_id"],
            "source_table": original["table"],
            "original_row_key": deepcopy(original["row_key"]),
            "record_class": original["record_class"],
            "native_timestamp": deepcopy(original["native_timestamp"]),
            "time_basis": original["time_basis"],
            "source_locator_status": source["status"],
            "source_file_claims": locators,
            "provenance_issues": deepcopy([
                p for p in issues if p.get("ref_id") == ref
            ]),
            "independent_source_authentication": False,
        })
    return output


def _typed_authoring_projection(
    capture_id: object, digest: str, rows: list[dict], integrity: dict,
    evidence_map: dict,
) -> dict:
    """Stable authoring *advice*; never a spec, assertion or verified v2 field.

    This adapter deliberately consumes the original producer classes rather
    than guessing Agent C's namespace/zone IDs. It is safe for a separately
    reviewed display in Agent B's editor but is NOT an editor import payload.
    """
    steps = []
    for row in rows:
        identities = []
        for binding in row["identity_matches"]:
            classification = binding["classification"]
            if classification not in {"EXACT", "AMBIGUOUS", "INFERRED",
                                      "UNRESOLVED", "UNSUPPORTED"}:
                raise ValueError("unknown identity confidence classification")
            value = binding["observed_value"]
            candidate = value if type(value) is int and 0 <= value <= 2**32 - 1 else None
            state = ("ambiguous" if classification == "AMBIGUOUS"
                     else "candidate" if classification in {"EXACT", "INFERRED"} and candidate is not None
                     else "unresolved")
            if state != "candidate":
                candidate = None
            identities.append({
                "binding_id": binding["binding_id"],
                "capture_identity_kind": binding["kind"],
                "observed_value": deepcopy(value),
                "classification": classification,
                "proposed_v2_binding_state": state,
                "identity_candidate": candidate,
                "namespace_candidate": None, "zone_id_candidate": None,
                "source_record_correlation": classification == "EXACT",
                "source_identity_verified": False,
                "source_candidates_original": deepcopy(binding["source_candidates"]),
                "original_evidence_refs": deepcopy(binding["evidence_refs"]),
                "review_decision_original": deepcopy(binding["review_decision"]),
            })
        oracle = row["oracle_readiness"]
        steps.append({
            "step_id": row["step_id"],
            "observed_summary_original": row["observed_summary"],
            "original_evidence_refs": deepcopy(row["evidence_refs"]),
            "indexed_evidence_provenance": _indexed_provenance(
                evidence_map, row["evidence_refs"], integrity["issues"]),
            "identity_confidence": identities,
            "missing_readbacks": deepcopy(row["missing_observations"]),
            "readiness_state": row["readiness_state"],
            "provenance_issues": deepcopy(row["compatibility_issues"]),
            "expected_candidate": deepcopy(oracle["expected_candidate"]),
            "independent_source_claim": deepcopy(oracle["independent_source"]),
            "oracle_readiness": oracle["readiness"],
            "oracle_approval_state": "UNAPPROVED",
            "normative_expected": None, "verdict": "UNKNOWN",
            "execution_enabled": False,
        })
    return {
        "contract": "capture_readiness_authoring_projection_v1_NONCANONICAL",
        "capture_id": capture_id,
        "indexed_capture_projection_sha256": digest,
        "physical_source_authenticated": False,
        "source_compatibility_state": integrity["state"],
        "source_provenance_issues": deepcopy(integrity["issues"]),
        "steps": steps,
        "contract_v2_adoption": "BLOCKED_PENDING_ACCEPTED_CONTRACT_AND_REVIEW",
        "automatic_import": False, "save_allowed": False,
        "approved_for_execution": False, "execution_enabled": False,
        "normative_expected": None, "verdict": "UNKNOWN",
    }



def summarize_capture_readiness(
    draft: dict, *, catalog_snapshots: dict | None = None,
    reconciliations: list[dict] | None = None,
    independent_oracles: list[dict] | None = None,
    comparison_drafts: list[dict] | None = None,
    expected_capture_projection_sha256: str | None = None,
    expected_dsp_commit: str | None = None,
) -> dict:
    """Return an immutable reviewer display and manual authoring *diagnostic*.

    A checksum is not a signature. Expected values remain candidates even if
    the author supplied an independent source, reviewed a binding, or pinned
    an identical revision. No validated canonical spec is returned.
    """
    _check(draft)
    assessment = assess_evidence_readiness(
        draft, catalog_snapshots=catalog_snapshots,
        reconciliations=reconciliations,
        independent_oracles=independent_oracles,
        comparison_drafts=comparison_drafts,
    )
    integrity = _integrity(draft, expected_capture_projection_sha256,
                           expected_dsp_commit, assessment["steps"])
    rows = []
    readbacks_by_step = {}
    for step, result in zip(draft["steps"], assessment["steps"], strict=True):
        if step["step_id"] != result["step_id"]:
            raise ValueError("step reference drift in readiness projection")
        missing = _observations(step)
        readbacks_by_step[step["step_id"]] = [r["observation"] for r in missing]
        blockers = [p for p in integrity["issues"] if
                    (p.get("step_id") is None and p.get("ref_id") is None)
                    or p.get("step_id") == step["step_id"]
                    or (p.get("ref_id") is not None and p["ref_id"] in step["evidence_refs"])]
        step_readiness = ("BLOCKED" if any(p["severity"] == "BLOCKED" for p in blockers)
                          else "UNKNOWN")
        # This state describes evidence compatibility only, never a gameplay
        # PASS/FAIL, successful readback, approved oracle, or runner permission.
        for gap in missing:
            gap["readiness_state"] = step_readiness
        if any(x["classification"] in {"UNRESOLVED", "UNSUPPORTED", "AMBIGUOUS"}
               for x in result["identity_candidates"]):
            blockers.append({"code": "IDENTITY_REVIEW_NEEDED", "severity": "UNKNOWN",
                             "reason": "Unresolved/ambiguous identity or unsupported source namespace"})
        rows.append({
            "step_id": step["step_id"],
            "observed_summary": step["observed_summary"],
            "evidence_refs": deepcopy(step["evidence_refs"]),
            "identity_matches": deepcopy(result["identity_candidates"]),
            "source_record_exact_not_verified": [
                b["binding_id"] for b in result["identity_candidates"]
                if b["classification"] == "EXACT" and b["source_identity_verified"] is False
            ],
            "independently_verified_client_dsp_identity": False,
            "missing_observations": missing,
            "readiness_state": step_readiness,
            "missing_provenance_and_review": deepcopy(result["missing_observations_or_review"]),
            "oracle_readiness": deepcopy(result["oracle"]),
            "expected_outcome_classification": (
                "INDEPENDENT_SOURCE_CANDIDATE_UNAPPROVED"
                if result["oracle"]["expected_candidate"] is not None
                else "UNKNOWN"),
            "normative_expected": None, "verdict": "UNKNOWN",
            "review_required": True, "execution_enabled": False,
            "compatibility_issues": blockers,
        })
    variations = []
    for item in assessment["repeated_capture_variations"]:
        if item["comparability"] == "SOURCE_OR_PARSER_REVISION_DIFFERENT":
            status = "REVISION_INCOMPATIBLE"
        else:
            status = "POTENTIAL_CONTRADICTION_NEEDS_COMPARABILITY_REVIEW"
        variations.append({
            **deepcopy(item),
            "review_status": status,
            "interpretation": ("Conflicting recorded values; source revisions, "
                               "preconditions, zone instance and independent server "
                               "state must be checked before calling this a regression"),
            "verdict": "UNKNOWN",
        })
    return {
        "contract": "capture_author_readiness_summary_v0_NONCANONICAL",
        "capture_id": draft["capture_id"],
        "capture_projection_sha256": assessment["capture_projection_sha256"],
        "source_integrity": integrity,
        "readiness_steps": rows,
        "repeated_capture_diagnostics": variations,
        "contract_v2_alignment": _v2_hints(draft, assessment, readbacks_by_step),
        "scenario_developer_handoff": {
            "route": "/scenario-developer", "mode": "MANUAL_DESIGN_ONLY",
            "payload_kind": "NONCANONICAL_DIAGNOSTIC_ADVISORY",
            "read_only_projection": _typed_authoring_projection(
                draft["capture_id"], assessment["capture_projection_sha256"],
                rows, integrity, draft["evidence_map"],
            ),
            "automatic_import": False, "save_allowed": False,
            "execution_enabled": False,
        },
        "normative_expected": None, "verdict": "UNKNOWN",
        "review_required": True, "execution_enabled": False,
        "approved_for_execution": False,
    }
