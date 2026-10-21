"""Synthetic #1261 Coverage Matrix ↔ Scenario Developer ↔ Evidence Reviewer handoff.

No live capture, DSP, GM, database mutation, execution or trusted-oracle claims.
"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from workbench.server_admin.scenario_authoring.context_handoff import (
    coverage_context, coverage_path, inspect_evidence_review,
)
from workbench.server_admin.scenario_authoring.editor_router import (
    inspect_coverage_handoff, inspect_evidence_handoff, CoverageReferenceRequest, EvidenceReviewRequest,
)

REF = "/feature-testing/coverage/context/gardening/GARD-SYNTH-01"


def coverage_fixture():
    return {
        "contract": "coverage_behavior_reference_v1",
        "feature_id": "gardening", "behavior_ref": "GARD-SYNTH-01",
        "label": "Synthetic declared scenario intent", "category": "positive",
        "reference_kind": "declared_test_case_intent_not_behavior_trace_identity",
        "source": "data/testing/feature_test_readiness.json",
        "source_pointer": "features[id=gardening].cases[id=GARD-SYNTH-01]",
        "source_revision": "UNPINNED", "proposed_case_id": None,
        "expected_oracle": "UNKNOWN", "assertions": [], "observations": [],
        "capability_bindings": [], "context_only": True, "design_only": True,
        "review_required": True, "auto_populate_allowed": False,
        "auto_save_allowed": False, "execution_enabled": False,
    }


def request(method="POST", remote=False, origin=None):
    headers=[(b"content-type",b"application/json"),(b"content-length",b"100")]
    if origin:headers.append((b"origin",origin.encode()))
    return Request({"type":"http","method":method,"path":"/scenario-developer/handoff/evidence/inspect",
                    "scheme":"http","server":("testserver",80),
                    "client":("198.51.100.9" if remote else "127.0.0.1",1234),
                    "headers":headers})


def reviewed_fixture():
    # Reuse Agent D's accepted indexed projection builder on clearly synthetic
    # records. Do not fabricate a stand-in independent evidence oracle.
    from test_evidence_to_scenario_handoff import synthetic_interaction_with_key_item
    from workbench.captures.scenario_handoff import reconstruct_review_draft
    from workbench.captures.scenario_review_workflow import manual_editor_handoff
    con=synthetic_interaction_with_key_item()
    try:
        original=reconstruct_review_draft(con,1)
        bundle=manual_editor_handoff(original)
        decisions=[]
        binding_decisions=[]
        for step in original["steps"]:
            decisions.append({"step_id":step["step_id"],"decision":"ACCEPT",
                              "note":"Synthetic reviewer accepted description only"})
            for b in step["bindings"]:
                binding_decisions.append({"binding_id":b["binding_id"],
                                          "decision":"ACCEPT","note":"Synthetic candidate remains unverified"})
        return {
            "contract":"offline_capture_review_decisions_v1_NONCANONICAL",
            "capture_id":1,"capture_projection_sha256":bundle["capture_projection_sha256"],
            "observed_handoff":bundle,
            "step_decisions":decisions,"binding_decisions":binding_decisions,
            "review_status":"MANUAL_AUTHORING_REQUIRED","normative_expected":None,
            "verdict":"UNKNOWN","execution_enabled":False,"approved_for_execution":False,
        }
    finally:con.close()


def test_accepted_coverage_adapter_emits_exact_editor_contract():
    from workbench.server_admin.scenario_coverage.authoring import draft_context
    synthetic_readiness={"schema_version":1,"features":[
        {"id":"gardening","cases":[{"id":"GARD-SYNTH-01",
         "title":"Synthetic declared scenario intent","kind":"positive"}]}
    ]}
    source=draft_context(synthetic_readiness,"gardening","GARD-SYNTH-01")
    assert coverage_context(source,REF)["behavior_ref"]=="GARD-SYNTH-01"
    assert source["auto_save_allowed"] is False
    assert source["assertions"] == []


def test_coverage_reference_exact_and_provisional():
    a=coverage_context(coverage_fixture(),REF)
    assert coverage_path(REF)==("gardening","GARD-SYNTH-01")
    assert a["feature_id"]=="gardening" and a["expected_oracle"]=="UNKNOWN"
    assert a["auto_save_allowed"] is False and a["execution_enabled"] is False
    assert a["source_revision"]=="UNPINNED"
    assert a["return_url"]=="/feature-testing/coverage"
    result=inspect_coverage_handoff(request(),CoverageReferenceRequest(
        context_ref=REF,source=coverage_fixture()))
    assert result==a


@pytest.mark.parametrize("url",[
    "https://attacker.example/feature-testing/coverage/context/gardening/GARD-SYNTH-01",
    "//attacker.example/path", "/feature-testing/coverage/context/gardening/../../admin",
    "/feature-testing/coverage/context/gardening/GARD-SYNTH-01?claim=pass",
    "/feature-testing/coverage/context/gardening/%47ARD-SYNTH-01",
    "/feature-testing/coverage/context/gardening/",
])
def test_unsafe_coverage_references_refused(url):
    with pytest.raises(ValueError,match="Unsupported"):
        coverage_path(url)


@pytest.mark.parametrize("field,value", [
    ("source","not-a-committed-source"),
    ("source_revision","VERIFIED"),
    ("expected_oracle","PASS"),
    ("auto_save_allowed",True),
    ("review_required",False),
    ("assertions",[{"id":"invented"}]),
    ("capability_bindings",["gm"]),
    ("behavior_ref","different"),
])
def test_coverage_authority_injection_refused(field,value):
    row=coverage_fixture();row[field]=value
    with pytest.raises(ValueError):
        coverage_context(row,REF)


def test_evidence_review_internal_projection_and_untrusted_status():
    payload=reviewed_fixture()
    inspected=inspect_evidence_review(payload)
    assert inspected["contract"]=="editor_evidence_suggestions_v1"
    assert inspected["projection_sha256"]==payload["capture_projection_sha256"]
    assert inspected["original_capture_authenticated"] is False
    assert inspected["projection_matches_embedded_evidence"] is True
    assert any(pointer["sha256"]!="UNKNOWN"
               and pointer["verification"]=="INDEXED_SOURCE_METADATA_NOT_REHASHED"
               for step in inspected["steps"] for pointer in step["source_fingerprints"])
    assert inspected["execution_enabled"] is False
    assert inspected["normative_expected"]=="UNKNOWN"
    assert inspected["required_confirmation"] is True
    assert all(s["decision"]=="ACCEPT" for s in inspected["steps"])
    assert all(b["confidence"]=="UNVERIFIED_CAPTURE_IDENTITY"
               for s in inspected["steps"] for b in s["bindings"])
    assert inspect_evidence_handoff(request(),EvidenceReviewRequest(review=payload))==inspected


@pytest.mark.parametrize("mutate",[
    lambda p:p.update(verdict="PASS"),
    lambda p:p.update(execution_enabled=True),
    lambda p:p["observed_handoff"]["canonical_specification_seed"].update(
        runner="xiheadless_observation_v1"),
    lambda p:p["observed_handoff"]["reviewed_steps"][0].update(normative_expected="PASS"),
    lambda p:p["observed_handoff"]["evidence_map"].clear(),
    lambda p:p.update(capture_projection_sha256="0"*64),
    lambda p:p["observed_handoff"]["reviewed_steps"][0]["bindings"][0].update(
        authority="VERIFIED"),
    lambda p:p["step_decisions"].append(deepcopy(p["step_decisions"][0])),
    lambda p:p["step_decisions"][0].update(note=""),
    lambda p:p["observed_handoff"]["continue_in_scenario_developer"].update(automatic_import=True),
])
def test_rejected_tampered_and_incompatible_reviews(mutate):
    payload=reviewed_fixture()
    mutate(payload)
    with pytest.raises((ValueError,KeyError,TypeError)):
        inspect_evidence_review(payload)


def test_pending_review_is_visible_not_auto_accepted():
    payload=reviewed_fixture()
    payload["step_decisions"].pop()
    inspected=inspect_evidence_review(payload)
    assert inspected["review_complete_in_file"] is False
    assert any(s["decision"]=="PENDING" for s in inspected["steps"])


def test_missing_original_evidence_location_kept_unverified():
    inspected=inspect_evidence_review(reviewed_fixture())
    assert inspected["original_source_url"] is None
    assert "original offline" in inspected["return_instructions"]


def test_evidence_endpoint_remains_local_and_nonexecuting():
    payload=reviewed_fixture()
    with pytest.raises(HTTPException) as remote:
        inspect_evidence_handoff(request(remote=True),EvidenceReviewRequest(review=payload))
    assert remote.value.status_code==403
    with pytest.raises(HTTPException) as xsite:
        inspect_evidence_handoff(request(origin="https://attacker.example"),
                                 EvidenceReviewRequest(review=payload))
    assert xsite.value.status_code==403


def test_editor_route_and_controls_do_not_dispatch():
    from pathlib import Path
    repo=Path(__file__).resolve().parents[1]
    html=(repo/"gui/templates/scenario_developer.html").read_text(encoding="utf8")
    js=(repo/"gui/static/scenario_developer.js").read_text(encoding="utf8")
    for ident in ("sd-context-use","sd-context-detail","sd-evidence-file",
                  "sd-evidence-inspect","sd-evidence-use","sd-evidence-suggestions"):
        assert f'id="{ident}"' in html
    assert "/scenario-developer/handoff/coverage/inspect" in js
    assert "/scenario-developer/handoff/evidence/inspect" in js
    assert "reviewed" in html.lower() and "no draft is automatically" in html.lower()
    for forbidden in ("/builder/launch","send_gm_command","/itemedit/batch/apply"):
        assert forbidden not in js


def test_explicit_manual_completion_preview_save_reopen_edit(monkeypatch, tmp_path):
    """Handoff alone cannot save; after human-authored synthetic obligations it can."""
    from test_scenario_guided_catalog_workspace import synthetic_spec
    from workbench.server_admin.feature_testing.spec_drafts import get_drafts, save_draft
    from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec
    inspected=inspect_evidence_review(reviewed_fixture())
    # Synthetic author supplies an already supported canonical assertion/observation
    # manually. This is NOT derived from the indexed capture.
    spec=synthetic_spec()
    spec["case_id"]="SYNTH-HANDOFF-MANUAL-01"
    spec["rationale"]="UNVERIFIED indexed capture 1 projection "+inspected["projection_sha256"]
    spec["steps"][0]["confidence_note"]="OBSERVED only; original index not authenticated; "+inspected["projection_sha256"]
    spec["steps"][0]["expected"]="UNKNOWN — user must still establish source-backed oracle"
    spec["authoring"]["blocking_gaps"].append(
        "Indexed capture provenance is not independent proof of expected behavior"
    )
    view=validate_editor_spec(spec)
    assert view["reader_view"]["independent_verification"]=="NOT_ESTABLISHED"
    assert view["reader_view"]["steps"][0]["status"]=="UNKNOWN"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",str(tmp_path/"draft.sqlite"))
    saved=save_draft(view["canonical_specification"],0)
    assert saved["revision"]==1 and saved["execution_enabled"] is False
    loaded=get_drafts()[0]["specification"]
    assert loaded["rationale"]==spec["rationale"]
    assert loaded["steps"][0]["confidence_note"]==spec["steps"][0]["confidence_note"]
    loaded["steps"][0]["title"]="Edited human-authored synthetic observation"
    saved2=save_draft(validate_editor_spec(loaded)["canonical_specification"],1)
    assert saved2["revision"]==2
    assert get_drafts()[0]["specification"]["steps"][0]["title"]==loaded["steps"][0]["title"]


def test_reviewer_proposed_identity_is_not_original_evidence_or_trusted_binding():
    payload=reviewed_fixture()
    first=payload["binding_decisions"][0]
    source_id=first["binding_id"]
    first.update(decision="EDIT",edited_value="SYNTHETIC_REVIEW_PROPOSAL")
    result=inspect_evidence_review(payload)
    items=[b for step in result["steps"] for b in step["bindings"]
           if b["binding_id"]==source_id]
    assert len(items)==1
    candidate=items[0]
    assert candidate["review_decision"]=="EDIT"
    assert candidate["suggested_identity"]=="SYNTHETIC_REVIEW_PROPOSAL"
    assert candidate["identity"]!=candidate["suggested_identity"]
    assert candidate["confidence"]=="UNVERIFIED_CAPTURE_IDENTITY"
    assert result["original_capture_authenticated"] is False


def test_coverage_output_preserves_blockers_and_exact_ref():
    context=coverage_context(coverage_fixture(),REF)
    assert context["proposed_case_id"] is None
    assert context["assertions"]==context["observations"]==context["capability_bindings"]==[]
    assert context["design_only"] and not context["auto_populate_allowed"]
    assert context["review_required"] and not context["auto_save_allowed"]


def test_revisioned_authoring_cannot_create_duplicate_draft(monkeypatch,tmp_path):
    from test_scenario_guided_catalog_workspace import synthetic_spec
    from workbench.server_admin.feature_testing.spec_drafts import save_draft
    from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",str(tmp_path/"deduplicate.sqlite"))
    manually_authored=synthetic_spec()
    manually_authored["case_id"]="SYNTH-NO-DUPLICATES"
    approved_for_storage=validate_editor_spec(manually_authored)["canonical_specification"]
    first=save_draft(approved_for_storage,0)
    assert first["revision"]==1 and first["execution_enabled"] is False
    with pytest.raises(ValueError,match="revision conflict"):
        save_draft(approved_for_storage,0)
    with pytest.raises(ValueError,match="revision conflict"):
        save_draft(approved_for_storage,0)


def test_unified_editor_has_one_coverage_start_and_manual_evidence_binding_review():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    js=(root/"gui/static/scenario_developer.js").read_text(encoding="utf8")
    model=(root/"gui/static/scenario_guided_model.js").read_text(encoding="utf8")
    page=(root/"gui/templates/scenario_developer.html").read_text(encoding="utf8")
    assert "async function resolveCoverageContext" in js
    assert "async function loadContextRef" not in js
    assert js.count("await resolveCoverageContext();")==1
    begin=js[js.index("  let coverageBeginPending=false;"):js.index("  function renderEvidenceSuggestions")]
    assert "const latest=await call(ref,'GET')" in begin
    assert "M.coverageContextChanged(original,checked)" in begin
    assert "setSourceDetail(null,null);" in begin  # declared intent != published scenario
    assert "setSourceDetail(checked.feature_id,checked.behavior_ref)" not in begin
    assert "installIncompleteDraft(" in begin
    assert "coverageBeginPending" in begin
    assert "finally" in begin
    assert "sd-context-use" in js
    assert "sd-preview-incomplete" in js
    assert "M.handoffReplacementIssue(" in js
    assert "current();" in js[js.index("function installIncompleteDraft"):js.index("async function resolveCoverageContext")]
    assert "savePending=true" in js
    assert "finally {savePending=false" in js
    assert "sd-binding-decision" in js
    assert "INCLUDE_UNVERIFIED" in js and "EXCLUDE" in js
    assert "reviewer-proposal=" in model
    assert "sd-evidence-return" in page
    assert "return to Evidence Reviewer" in page or "Return to the Evidence Reviewer" in page
    assert "OBSERVED / provisional" in js and "EXPECTED / normative" in js
    assert not any(token in js for token in ("send_gm_command","/builder/launch","packet_inject"))


def test_review_payload_actual_size_limit_not_only_content_length():
    """A local caller cannot evade the bounded review import with a false header."""
    forged=reviewed_fixture()
    forged["padding"]="x"*5_100_000
    with pytest.raises(HTTPException) as oversized:
        inspect_evidence_handoff(request(),EvidenceReviewRequest(review=forged))
    assert oversized.value.status_code==413


def test_unicode_review_length_matches_actual_utf8_not_ascii_escaped_size():
    """Large supplementary-plane text must fail for schema, not fictitious size."""
    forged=reviewed_fixture()
    forged["unsupported_unicode_field"]="🏮"*650_000
    compact=json.dumps({"review":forged},ensure_ascii=False,
                       separators=(",",":")).encode("utf-8")
    ascii_escaped=json.dumps({"review":forged},ensure_ascii=True).encode("utf-8")
    assert len(compact)<5_000_000<len(ascii_escaped)
    with pytest.raises(HTTPException) as result:
        inspect_evidence_handoff(request(),EvidenceReviewRequest(review=forged))
    # Extra unauthorized fields are refused by the review schema, not wrongly
    # diagnosed as oversized because a client included Japanese/emoji text.
    assert result.value.status_code==422


def test_editor_evidence_bounds_match_accepted_offline_reviewer():
    from pathlib import Path
    from workbench.server_admin.scenario_authoring import context_handoff
    root=Path(__file__).resolve().parents[1]
    js=(root/"gui/static/scenario_developer.js").read_text(encoding="utf-8")
    page=(root/"gui/templates/scenario_developer.html").read_text(encoding="utf-8")
    producer=(root/"src/workbench/captures/scenario_review_offline.py").read_text(encoding="utf-8")
    assert context_handoff._MAX_STEPS==100
    assert context_handoff._MAX_REFS==4000
    assert "4_000_000" in producer
    assert "file.size>4_500_000" in js
    assert "maximum 4.5 MB" in page


def test_unicode_draft_save_roundtrip_revision_and_ascii_storage_limit(monkeypatch,tmp_path):
    """V1 SQLite saves ASCII-escaped JSON (32 KiB), not request UTF-8 bytes."""
    from test_scenario_guided_catalog_workspace import synthetic_spec
    from workbench.server_admin.feature_testing.spec_drafts import save_draft,get_drafts
    from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",str(tmp_path/"unicode_v1.sqlite"))
    spec=synthetic_spec()
    spec["case_id"]="SYNTH-UNICODE-PROVENANCE"
    spec["rationale"]="Reviewed source: 染め物 • 观察 🏮; oracle UNKNOWN"
    spec["steps"][0]["confidence_note"]="記録された観察 • 🏮; source digest not rehashed"
    view=validate_editor_spec(spec)["canonical_specification"]
    result=save_draft(view,0)
    assert result["revision"]==1 and not result["execution_enabled"]
    restored=get_drafts()[0]["specification"]
    assert restored["rationale"]==spec["rationale"]
    assert restored["steps"][0]["confidence_note"]==spec["steps"][0]["confidence_note"]
    restored["steps"][0]["title"]="Unicode revision: 再確認"
    assert save_draft(validate_editor_spec(restored)["canonical_specification"],1)["revision"]==2
    with pytest.raises(ValueError,match="revision conflict"):
        save_draft(restored,1)

    oversized=deepcopy(spec)
    step=deepcopy(spec["steps"][0])
    for i in range(60):
        item=deepcopy(step)
        item["id"]=f"SYNTH-UNICODE-{i:03d}"
        item["confidence_note"]="界"*120
        if i==0: oversized["steps"]=[]
        oversized["steps"].append(item)
    # The v1 canonical spec itself is legal, yet SQLite's ASCII-escaped form
    # exceeds 32 KiB. No silent note truncation or partial revision is allowed.
    from workbench.server_admin.feature_testing.test_specifications import validate_spec
    validate_spec(oversized)
    assert len(json.dumps(oversized,sort_keys=True,separators=(",",":")).encode("utf-8"))>32768
    with pytest.raises(ValueError,match="32KiB"):
        save_draft(oversized,0)
    assert get_drafts()[0]["revision"]==2


def test_agent_a_discard_review_guard_all_editor_replacement_paths():
    """No New/Fork/Clone/Open or source handoff may silently lose edits."""
    from pathlib import Path
    js=(Path(__file__).resolve().parents[1]/"gui/static/scenario_developer.js").read_text(encoding="utf-8")
    model=(Path(__file__).resolve().parents[1]/"gui/static/scenario_guided_model.js").read_text(encoding="utf-8")
    assert "function confirmDocumentReplacement" in js
    assert "M.replacementConfirmationReason(" in js
    assert "window.confirm(" in js
    assert "if(savePending) throw Error" in js
    for label, end in (("sd-new","sd-fork"),("sd-fork","sd-clone"),
                       ("sd-clone","sd-add-assertion"),("sd-open-draft","function paintCandidates")):
        start=js.index("  $('"+label+"').addEventListener")
        stop=js.index("  $('"+end+"').addEventListener",start) if end.startswith("sd-") else js.index(end,start)
        segment=js[start:stop]
        assert "confirmDocumentReplacement(" in segment, label
        assert "editorGeneration++" in segment, label
    assert "if(startedGeneration!==editorGeneration)" in js
    assert "forkPending=true" in js and "finally{forkPending=false" in js
    assert "const generation=editorGeneration" in js
    assert "const input=M.clone(current())" in js
    assert "M.saveResponseDisposition(toSave,latest,saved" in js
    assert "if(!disposition.apply_revision)" in js
    assert "if(savePending)throw Error" in js[js.index("function installIncompleteDraft"):
                                               js.index("async function resolveCoverageContext")]
    assert "replacementConfirmationReason" in model and "saveResponseDisposition" in model
