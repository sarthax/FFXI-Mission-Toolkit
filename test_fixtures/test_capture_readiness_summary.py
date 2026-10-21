#!/usr/bin/env python3
"""Synthetic offline reviewer readiness with advisory, noncanonical v2 metadata."""
from __future__ import annotations

from copy import deepcopy
import json
import re

from test_capture_identity_oracle_readiness import (
    fixture, binding, source, record, proof_for, independent_oracle,
    second_capture, synthetic_interaction_with_key_item,
)
from workbench.captures.scenario_handoff import reconstruct_review_draft
from workbench.captures.scenario_identity_readiness import _observation_digest
from workbench.captures.scenario_readiness_summary import summarize_capture_readiness
from workbench.captures.scenario_review_workflow import manual_editor_handoff
from workbench.captures.scenario_review_offline import render_review_html


def _row(out, step_id):
    return next(s for s in out["readiness_steps"] if s["step_id"] == step_id)


def test_source_record_exact_is_not_independently_verified():
    con, draft = fixture()
    npc = binding(draft, 0, "npc")
    bname = binding(draft, 0, "npc_name")
    rec = record("npc", 7000, "SYNTHETIC_ACTOR", zone="SYNTHETIC_ZONE")
    choices = {
        npc["binding_id"]: source("npc", [rec], complete=True, dsp_commit="d" * 40),
        bname["binding_id"]: source("npc", [
            rec, record("npc", 7001, "CONTRADICTING_SYNTHETIC_LABEL",
                        zone="SYNTHETIC_ZONE")]),
    }
    original = deepcopy(draft)
    output = summarize_capture_readiness(
        draft, catalog_snapshots=choices,
        reconciliations=[proof_for(npc, "npc", rec)],
        independent_oracles=[independent_oracle(draft["steps"][0])],
        expected_capture_projection_sha256=_observation_digest(draft),
        expected_dsp_commit="d" * 40,
    )
    first = output["readiness_steps"][0]
    matches = {m["kind"]: m for m in first["identity_matches"]}
    assert matches["npc"]["classification"] == "EXACT"
    assert matches["npc"]["source_identity_verified"] is False
    assert first["source_record_exact_not_verified"] == [npc["binding_id"]]
    assert first["independently_verified_client_dsp_identity"] is False
    assert matches["npc_name"]["classification"] == "AMBIGUOUS"
    assert first["expected_outcome_classification"] == "INDEPENDENT_SOURCE_CANDIDATE_UNAPPROVED"
    assert first["oracle_readiness"]["expected_candidate"] == "SYNTHETIC_SOURCE_DERIVED_STATE"
    assert first["oracle_readiness"]["independent_source"]["line"] == 82
    assert first["oracle_readiness"]["normative_expected"] is None
    assert first["normative_expected"] is None and first["verdict"] == "UNKNOWN"
    assert not first["execution_enabled"]
    assert output["source_integrity"]["state"] == "UNKNOWN"
    assert output["source_integrity"]["independent_capture_bytes_authenticated"] is False
    assert output["scenario_developer_handoff"]["automatic_import"] is False
    assert output["scenario_developer_handoff"]["save_allowed"] is False
    typed = output["scenario_developer_handoff"]["read_only_projection"]
    assert typed["contract"] == "capture_readiness_authoring_projection_v1_NONCANONICAL"
    assert typed["automatic_import"] is False and typed["execution_enabled"] is False
    assert typed["contract_v2_adoption"] == "BLOCKED_PENDING_ACCEPTED_CONTRACT_AND_REVIEW"
    assert typed["physical_source_authenticated"] is False
    row = typed["steps"][0]
    assert row["canonical_step_id"] is None
    assert row["canonical_source_association"] == {
        "state": "UNASSIGNED_REQUIRES_INDEPENDENT_CANONICAL_CROSSWALK",
        "scope": None, "source_refs": [],
    }
    assert row["observed_summary_original"] == draft["steps"][0]["observed_summary"]
    assert row["original_evidence_refs"] == draft["steps"][0]["evidence_refs"]
    assert [x["evidence_ref"] for x in row["indexed_evidence_provenance"]] == row["original_evidence_refs"]
    for provenance in row["indexed_evidence_provenance"]:
        source_row = draft["evidence_map"][provenance["evidence_ref"]]
        assert provenance["capture_id"] == source_row["capture_id"]
        assert provenance["source_table"] == source_row["table"]
        assert provenance["original_row_key"] == source_row["row_key"]
        assert provenance["source_locator_status"] == source_row["source"]["status"]
        assert provenance["independent_source_authentication"] is False
        assert provenance["capture_file_locator_state"] == (
            "INDEXED_FILENAME_CLAIM_NOT_AUTHENTICATED"
            if any(x.get("filename") for x in source_row["source"]["references"])
            else "NO_INDEXED_CAPTURE_FILE_LOCATOR"
        )
        assert len(provenance["source_file_claims"]) == len(source_row["source"]["references"])
        for claim, locator in zip(provenance["source_file_claims"],
                                  source_row["source"]["references"], strict=True):
            assert claim["source_filename"] == locator["filename"]
            assert claim["locator_sha256_claim"] == locator["source_sha256"]
            assert claim["parser_name_claim"] == (
                locator["source_manifest"] or {}).get("parser_name")
            assert claim["parser_version_claim"] == (
                locator["source_manifest"] or {}).get("parser_version")
            assert claim["decoder_version"] is None
            assert claim["decoder_version_status"] == "NOT_INDEPENDENTLY_ATTESTED"
            assert claim["indexed_digests_rehashed"] is False
    ids = {x["capture_identity_kind"]: x for x in row["identity_confidence"]}
    assert ids["npc"]["classification"] == "EXACT"
    assert ids["npc"]["source_record_correlation"] is True
    assert ids["npc"]["source_identity_verified"] is False
    assert ids["npc"]["proposed_v2_binding_state"] == "candidate"
    assert ids["npc"]["namespace_candidate"] is None
    assert ids["npc"]["zone_id_candidate"] is None
    assert ids["npc_name"]["proposed_v2_binding_state"] == "ambiguous"
    assert ids["npc_name"]["identity_candidate"] is None
    assert row["expected_candidate"] == "SYNTHETIC_SOURCE_DERIVED_STATE"
    assert row["oracle_approval_state"] == "UNAPPROVED"
    assert row["normative_expected"] is None and row["verdict"] == "UNKNOWN"
    assert output["approved_for_execution"] is False
    assert draft == original
    con.close()


def test_detailed_missing_observations_for_all_lanes():
    con, draft = fixture()
    out = summarize_capture_readiness(draft)
    kinds = {s["step_id"]: {m["observation"]: m for m in s["missing_observations"]}
             for s in out["readiness_steps"]}
    for step in draft["steps"]:
        names = kinds[step["step_id"]]
        if step["lane"] == "capture_events":
            assert names["server_event_state"]["status"] == "NOT_INDEPENDENTLY_OBSERVED"
            assert names["client_dialog"]["status"] == "NOT_INDEPENDENTLY_OBSERVED"
            assert names["quest_variables"]["importance"] == "CONDITIONAL"
            assert names["instance_state"]["importance"] == "CONDITIONAL"
            assert names["job_state"]["importance"] == "CONDITIONAL"
            assert names["mob_state"]["importance"] == "CONDITIONAL"
        elif step["lane"] == "capture_eventview":
            assert {"server_event_state", "client_dialog", "quest_variables",
                    "instance_state", "job_state"}.issubset(names)
        elif step["lane"] == "capture_ki_events":
            assert {"client_key_items", "server_key_items"}.issubset(names)
            assert names["quest_variables"]["importance"] == "CONDITIONAL"
        elif step["lane"] == "capture_structured_records":
            assert {"client_inventory", "server_inventory"}.issubset(names)
            assert names["client_equipment"]["importance"] == "CONDITIONAL"
            assert names["server_furnishings"]["importance"] == "CONDITIONAL"
            assert names["temporary_items"]["importance"] == "CONDITIONAL"
        elif step["lane"] == "capture_raw_packets":
            assert {"packet_decoder", "server_receipt"} == set(names)
        else:
            raise AssertionError("uncovered synthetic event family")
    for step, item in zip(draft["steps"], out["readiness_steps"], strict=True):
        for obs in item["missing_observations"]:
            assert obs["expected_observation_type"] == obs["observation"]
            assert obs["reason_for_gap"] and obs["how_to_obtain"]
            assert obs["evidence_refs"] == step["evidence_refs"]
            assert obs["suggested_read_only_capability"].endswith("_readback")
            assert obs["capability_registered"] is False
            assert obs["permission_granted"] is False
            assert obs["review_required"] is True
            assert obs["status"] == "NOT_INDEPENDENTLY_OBSERVED"
            assert obs["readiness_state"] == item["readiness_state"] == "UNKNOWN"
    assert all(s["expected_outcome_classification"] == "UNKNOWN"
               for s in out["readiness_steps"])
    assert all(s["normative_expected"] is None for s in out["readiness_steps"])
    con.close()


def test_advisory_v2_field_mapping_uses_only_proposed_names():
    con, draft = fixture()
    out = summarize_capture_readiness(draft)
    align = out["contract_v2_alignment"]
    assert align["status"] == "ADVISORY_UNACCEPTED_NOT_CANONICAL"
    assert align["automatic_import"] is False and align["execution_enabled"] is False
    spec = align["metadata_shape_preview"]
    assert set(spec) == {"contract_version", "sources", "parameters",
                         "oracles", "step_requirements", "fingerprints"}
    assert spec["contract_version"] == 2
    assert spec["sources"] == [] and spec["oracles"] == []
    assert set(spec["fingerprints"]) == {"base_spec_sha256", "dsp_commit",
                                        "headless_commit", "toolkit_commit"}
    assert set(spec["fingerprints"].values()) == {None}
    names = set()
    for p in spec["parameters"]:
        assert set(p) == {"name", "kind", "identity", "namespace", "zone_id",
                          "binding_state", "source_refs"}
        assert p["binding_state"] != "independently_source_verified"
        assert p["source_refs"] == [] and p["namespace"] is None and p["zone_id"] is None
        assert p["kind"] in {"npc", "item", "key_item", "zone"}
        assert p["name"] not in names
        names.add(p["name"])
        if p["binding_state"] in {"unresolved", "ambiguous"}:
            assert p["identity"] is None
        else:
            assert type(p["identity"]) is int
    for s in spec["step_requirements"]:
        assert set(s) == {"step_id", "capability", "operation_class",
                          "required_permissions", "required_readbacks",
                          "approval_required", "execution_gate"}
        assert s["execution_gate"] == "blocked"
        assert s["approval_required"] is True
        assert s["capability"] == "unassigned"
        assert s["operation_class"] == "unknown"
        assert all(isinstance(name, str) and name for name in s["required_readbacks"])
    assert not hasattr(out, "validate_spec")
    con.close()


def test_revision_mismatch_and_tampered_projection_fail_closed():
    con, draft = fixture()
    original_hash = _observation_digest(draft)
    oracle = independent_oracle(draft["steps"][0])
    out = summarize_capture_readiness(draft,
        independent_oracles=[oracle], expected_dsp_commit="f" * 40)
    assert out["source_integrity"]["state"] == "BLOCKED"
    assert out["readiness_steps"][0]["readiness_state"] == "BLOCKED"
    assert all(x["readiness_state"] == "BLOCKED"
               for x in out["readiness_steps"][0]["missing_observations"])
    assert "DSP_REVISION_INCOMPATIBLE" in {
        item["code"] for item in out["source_integrity"]["issues"]}
    modified = deepcopy(draft)
    modified["steps"][0]["observed_summary"] += " ALTERED_SYNTHETIC_OBSERVATION"
    detected = summarize_capture_readiness(
        modified, expected_capture_projection_sha256=original_hash)
    assert detected["source_integrity"]["state"] == "BLOCKED"
    assert "CAPTURE_PROJECTION_CHANGED" in {
        item["code"] for item in detected["source_integrity"]["issues"]}
    assert all(s["readiness_state"] == "BLOCKED" for s in detected["readiness_steps"])
    assert all(gap["readiness_state"] == "BLOCKED"
               for s in detected["readiness_steps"] for gap in s["missing_observations"])
    # A forged locator/manifest source hash mismatch is not merely a missing readback.
    altered = deepcopy(draft)
    ref = altered["steps"][0]["evidence_refs"][0]
    row = altered["evidence_map"][ref]
    exact = next(x for x in row["source"]["references"] if x["source_manifest"])
    exact["source_manifest"]["sha256"] = "f" * 64
    failed = summarize_capture_readiness(altered)
    assert failed["source_integrity"]["state"] == "BLOCKED"
    assert "SOURCE_MANIFEST_DIGEST_MISMATCH" in {
        item["code"] for item in failed["source_integrity"]["issues"]}
    for pin in ("xyz", True, -1):
        try:
            summarize_capture_readiness(draft, expected_capture_projection_sha256=pin)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed digest pin was accepted")
    con.close()


def test_missing_parser_and_manifest_digests_are_unknown_not_false_conflicts():
    con, draft = fixture()
    ref = draft["steps"][0]["evidence_refs"][0]
    baseline = next(x for x in draft["evidence_map"][ref]["source"]["references"]
                    if x.get("source_manifest"))
    assert baseline["source_manifest"]["sha256"] == baseline["source_sha256"]
    for field in ("parser_name", "parser_version", "sha256"):
        incomplete = deepcopy(draft)
        source = next(x for x in incomplete["evidence_map"][ref]["source"]["references"]
                      if x.get("source_manifest"))
        source["source_manifest"].pop(field)
        result = summarize_capture_readiness(incomplete)
        codes = {x["code"] for x in result["source_integrity"]["issues"]}
        if field in ("parser_name", "parser_version"):
            assert "PARSER_REVISION_UNPINNED" in codes
        else:
            assert "SOURCE_MANIFEST_DIGEST_UNPINNED" in codes
        assert result["source_integrity"]["state"] == "UNKNOWN"
        assert result["readiness_steps"][0]["readiness_state"] == "UNKNOWN"
        assert not any(x["code"] == "SOURCE_MANIFEST_DIGEST_MISMATCH"
                       for x in result["source_integrity"]["issues"])
    con.close()


def test_unrecognized_parser_or_capture_ingest_remains_unknown():
    con, draft = fixture()
    incomplete = deepcopy(draft)
    ref = incomplete["steps"][0]["evidence_refs"][0]
    locator = next(x for x in incomplete["evidence_map"][ref]["source"]["references"]
                   if x.get("source_manifest"))
    locator["source_manifest"]["parser_version"] = "SYNTHETIC_FUTURE_UNSUPPORTED"
    locator["source_manifest"]["ingest_status"] = "UNRECOGNIZED"
    result = summarize_capture_readiness(incomplete)
    assert result["source_integrity"]["state"] == "UNKNOWN"
    issues = [x for x in result["source_integrity"]["issues"]
              if x.get("ref_id") == ref]
    assert any(x["code"] == "PARSER_OR_CAPTURE_INGEST_UNRECOGNIZED"
               and x["severity"] == "UNKNOWN" for x in issues)
    projected = result["scenario_developer_handoff"]["read_only_projection"]
    matching = [x for x in projected["steps"][0]["indexed_evidence_provenance"]
                if x["evidence_ref"] == ref][0]
    parser = next(x for x in matching["source_file_claims"]
                  if x["parser_version_claim"] == "SYNTHETIC_FUTURE_UNSUPPORTED")
    assert parser["parser_version_claim"] == "SYNTHETIC_FUTURE_UNSUPPORTED"
    assert parser["parser_support"] == "UNRECOGNIZED_OR_UNSUPPORTED"
    assert parser["decoder_version"] is None
    assert projected["steps"][0]["readiness_state"] == "UNKNOWN"
    assert projected["steps"][0]["verdict"] == "UNKNOWN"
    assert projected["execution_enabled"] is False
    assert render_review_html(incomplete, readiness=result)
    con.close()


def test_missing_capture_file_locator_is_unknown_and_not_physical_absence():
    con, draft = fixture()
    # The indexed capture has event rows with no source-file locator; this
    # cannot prove the physical file is missing, merely not indexed here.
    result = summarize_capture_readiness(draft)
    typed = result["scenario_developer_handoff"]["read_only_projection"]
    orphan = next(x for s in typed["steps"]
                  for x in s["indexed_evidence_provenance"]
                  if not x["source_file_claims"])
    assert orphan["capture_file_locator_state"] == "NO_INDEXED_CAPTURE_FILE_LOCATOR"
    assert orphan["source_locator_status"] in {"UNRESOLVED", "AMBIGUOUS"}
    assert orphan["independent_source_authentication"] is False
    assert all(s["verdict"] == "UNKNOWN" for s in typed["steps"])
    con.close()


def test_duplicate_capture_refs_fail_closed_without_inferred_step_links():
    con, draft = fixture()
    original = deepcopy(draft)
    ref = draft["steps"][0]["evidence_refs"][0]
    duplicate = deepcopy(draft)
    duplicate["steps"][0]["evidence_refs"].append(ref)
    try:
        summarize_capture_readiness(duplicate)
    except ValueError as exc:
        assert "duplicate" in str(exc).lower()
    else:
        raise AssertionError("duplicate original evidence ref was silently accepted")
    assert draft == original
    report = summarize_capture_readiness(draft)
    typed = report["scenario_developer_handoff"]["read_only_projection"]
    assert all(s["canonical_step_id"] is None for s in typed["steps"])
    assert all(s["canonical_source_association"]["source_refs"] == []
               and s["canonical_source_association"]["scope"] is None
               for s in typed["steps"])
    assert report["contract_v2_alignment"]["metadata_shape_preview"]["sources"] == []
    assert report["contract_v2_alignment"]["metadata_shape_preview"]["oracles"] == []
    # Agent C #1309 optional associations are never inferred or emitted.
    assert "source_associations" not in report["contract_v2_alignment"]["metadata_shape_preview"]
    con.close()


def test_repeated_capture_contradictions_are_not_gameplay_failures():
    con = synthetic_interaction_with_key_item()
    original = reconstruct_review_draft(con, 1)
    other = second_capture(con, changed_message=16)
    report = summarize_capture_readiness(original, comparison_drafts=[other])
    contradiction = next(v for v in report["repeated_capture_diagnostics"] if v["field"] == "dialog")
    assert contradiction["recorded_values"] == [15, 16]
    assert contradiction["review_status"] == "POTENTIAL_CONTRADICTION_NEEDS_COMPARABILITY_REVIEW"
    assert contradiction["verdict"] == "UNKNOWN"
    assert "preconditions" in contradiction["interpretation"]
    con.execute("UPDATE capture_source_manifest SET parser_version=? WHERE capture_id=2",
                ("SYNTHETIC_NEW_PARSER",))
    incompatible = reconstruct_review_draft(con, 2)
    result = summarize_capture_readiness(original, comparison_drafts=[incompatible])
    mismatch = next(v for v in result["repeated_capture_diagnostics"] if v["field"] == "dialog")
    assert mismatch["review_status"] == "REVISION_INCOMPATIBLE"
    assert mismatch["verdict"] == "UNKNOWN"
    assert report["execution_enabled"] is False
    con.close()


def test_existing_offline_reviewer_renders_readiness_without_approval():
    con, draft = fixture()
    report = summarize_capture_readiness(draft)
    html = render_review_html(draft, readiness=report)
    assert "Identity and oracle readiness" in html
    assert "NOT independently verified" not in html or "independent client/DSP verification" in html
    assert "Missing" not in html or "missing_observations" in html
    assert "INDEPENDENT_SOURCE_CANDIDATE_UNAPPROVED" not in html
    assert "contract_v2_alignment_status" in html
    assert "NOT approved oracles" in html
    assert "execution_enabled&quot;" in html or "execution_enabled" in html
    assert "Continue in Scenario Developer" in html
    assert "original" not in html or "Original indexed evidence" in html
    # Separate noncanonical sidecar retains untouched indexed source provenance.
    assert "Export separate readiness sidecar" in html
    assert "original_evidence_handoff:ORIGINAL" in html
    assert "review_decisions:gather()" in html
    assert "indexed_observation_projection_sha256:READINESS.capture_projection_sha256" in html
    assert "original_handoff_projection_sha256:ORIGINAL.capture_projection_sha256" in html
    assert "automatic_import:false,approved_for_execution:false,execution_enabled:false" in html
    original_blob = re.search(r"<script id='bundle' type='application/json'>(.*?)</script>", html, re.S)
    assert original_blob
    assert json.loads(original_blob.group(1)) == manual_editor_handoff(draft)
    readiness_blob = re.search(r"<script id='readiness' type='application/json'>(.*?)</script>", html, re.S)
    assert readiness_blob
    assert json.loads(readiness_blob.group(1)) == report
    assert report["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
        "missing_readbacks"] == report["readiness_steps"][0]["missing_observations"]
    sourced = summarize_capture_readiness(
        draft, independent_oracles=[independent_oracle(draft["steps"][0])])
    source_html = render_review_html(draft, readiness=sourced)
    assert "SYNTHETIC_SOURCE_DERIVED_STATE" in source_html
    assert "INDEPENDENT_SOURCE_CANDIDATE_UNAPPROVED" in source_html
    assert "NOT approved oracles" in source_html
    # Existing one-argument offline renderer remains compatible.
    assert "Identity and oracle readiness" in render_review_html(draft)
    for change in (
        lambda x: x["scenario_developer_handoff"]["read_only_projection"].update(
            approved_for_execution=True),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0].update(
            oracle_approval_state="APPROVED"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0].update(
            canonical_step_id="SYNTHETIC_FORGED_CANONICAL_STEP"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "canonical_source_association"].update(
                scope="step", source_refs=["SYNTHETIC_FORGED_SOURCE"]),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0].update(
                capture_file_locator_state="PHYSICALLY_VERIFIED_PRESENT"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0]["identity_confidence"][0].update(
            source_identity_verified=True),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0].update(
            original_evidence_refs=["FABRICATED_REF"]),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0].update(evidence_ref="FABRICATED"),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0]["source_file_claims"][0].update(
                indexed_digests_rehashed=True),
        lambda x: x["scenario_developer_handoff"]["read_only_projection"]["steps"][0][
            "indexed_evidence_provenance"][0]["source_file_claims"][0].update(
                decoder_version="FORGED_VERIFIED"),
        lambda x: x["readiness_steps"][0].update(execution_enabled=True),
        lambda x: x["readiness_steps"][0]["oracle_readiness"].update(normative_expected="UNAUTHORIZED"),
        lambda x: x["readiness_steps"][0]["identity_matches"][0].update(source_identity_verified=True),
        lambda x: x["readiness_steps"][0].update(evidence_refs=["FORGED_SOURCE"]),
        lambda x: x["readiness_steps"][0]["missing_observations"][0].update(
            status="INDEPENDENTLY_VERIFIED"),
        lambda x: x["readiness_steps"][0]["missing_observations"][0].update(
            permission_granted=True),
        lambda x: x["readiness_steps"][0]["missing_observations"][0].update(
            evidence_refs=["FORGED_CAPTURE_REF"]),
        lambda x: x["readiness_steps"][0].update(readiness_state="READY"),
        lambda x: x["source_integrity"].update(independent_capture_bytes_authenticated=True),
        lambda x: x["scenario_developer_handoff"].update(automatic_import=True),
        lambda x: x["contract_v2_alignment"].update(execution_enabled=True),
    ):
        altered = deepcopy(report)
        change(altered)
        try:
            render_review_html(draft, readiness=altered)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe readiness displayed or exported")
    forged = deepcopy(report)
    forged["capture_projection_sha256"] = "f" * 64
    try:
        render_review_html(draft, readiness=forged)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong-capture readiness displayed")
    con.close()


def main():
    test_existing_offline_reviewer_renders_readiness_without_approval()
    test_source_record_exact_is_not_independently_verified()
    test_detailed_missing_observations_for_all_lanes()
    test_advisory_v2_field_mapping_uses_only_proposed_names()
    test_missing_parser_and_manifest_digests_are_unknown_not_false_conflicts()
    test_revision_mismatch_and_tampered_projection_fail_closed()
    test_missing_capture_file_locator_is_unknown_and_not_physical_absence()
    test_duplicate_capture_refs_fail_closed_without_inferred_step_links()
    test_unrecognized_parser_or_capture_ingest_remains_unknown()
    test_repeated_capture_contradictions_are_not_gameplay_failures()
    print("Synthetic evidence readiness, provenance and contract_v2 hints: PASS")


if __name__ == "__main__":
    main()
