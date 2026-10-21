"""Synthetic-only catalog-to-scenario authoring acceptance (#1261).

No live DSP root, client DAT, bot, GM command or database writes are accessed.
"""
import copy
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from workbench.server_admin.scenario_authoring import editor_router as editor
from workbench.server_admin.feature_testing.spec_drafts import get_drafts, save_draft
from workbench.server_admin.feature_testing.test_specifications import specification


def synthetic_spec():
    spec = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    spec["case_id"] = "SYNTH-CATALOG-EDITOR-01"
    spec["name"] = "Synthetic source candidate observation"
    spec["purpose"] = "Investigate an NPC-associated inventory observation; not gameplay proof"
    spec["rationale"] = "Propose source relationships for future independent testing"
    spec["behavior"] = {
        "given": ["Synthetic inventory state with unknown NPC binding"],
        "when": ["Plan a read-only observation step"],
        "then": ["UNKNOWN — an independently source-backed oracle is required"],
    }
    spec["steps"] = [{
        "id": "SYNTH-CATALOG-EDITOR-01-S01",
        "title": "Observe a source candidate without executing a command",
        "intent": "observation",
        "expected": "UNKNOWN — no independent gameplay oracle",
        "assertion_ids": ["bag_equal"],
        "evidence_refs": ["client_bag", "db_bag"],
        "confidence_note": "Synthetic: no runtime evidence available",
    }]
    spec["authoring"] = {
        "state": "draft",
        "execution_policy": "read_only",
        "evidence_provenance": "synthetic_test_only",
        "blocking_gaps": ["NPC identity unresolved"],
        "review_required": True,
    }
    return spec


def synthetic_candidate(kind="npc", duplicate=False):
    return {
        "kind": kind,
        "id": 7001,  # synthetic only — never a claimed real NPC ID
        "name": "Synthetic Sample NPC",
        "source_path": "sql/npc_list.sql",
        "identity_status": "unreconciled_source_candidate",
        "duplicate_id_in_results": duplicate,
        "binding_verified": False,
        "execution_enabled": False,
        "operator_review_required": True,
    }


def request(host="127.0.0.1", headers=None):
    values = {"x-requested-with": "toolkit-ui", **(headers or {})}
    all_headers = [(k.encode(), v.encode()) for k, v in values.items()]
    scope = {"type": "http", "method": "GET", "path": "/scenario-developer/catalog/search",
             "scheme": "http", "server": ("127.0.0.1", 8000),
             "client": (host, 1234), "headers": all_headers}
    return Request(scope)


@pytest.mark.parametrize("kind", ["item", "keyitem", "npc", "mob", "zone", "gm"])
def test_six_picker_categories_delegate_only_to_merged_read_only_adapter(monkeypatch, tmp_path, kind):
    root = tmp_path / "synthetic_dsp"
    root.mkdir()
    monkeypatch.setattr(editor, "get_dsp_root", lambda: root)
    seen = []
    def source_lookup(path, requested_kind, query, *, limit):
        seen.append((path, requested_kind, query, limit))
        return {"kind": requested_kind, "query": query,
                "choices": [synthetic_candidate(requested_kind)],
                "binding_verified": False, "execution_enabled": False,
                "operator_review_required": True, "source_revision": None}
    monkeypatch.setattr(editor, "search_catalog", source_lookup)
    response = editor.search_editor_catalog(request(), kind, "sample", 12)
    assert seen == [(root, kind, "sample", 12)]
    assert response["binding_verified"] is False
    assert response["execution_enabled"] is False
    assert response["choices"][0]["operator_review_required"] is True


def test_missing_dsp_root_and_invalid_kind_fail_closed(monkeypatch):
    monkeypatch.setattr(editor, "get_dsp_root", lambda: None)
    with pytest.raises(HTTPException) as exc:
        editor.search_editor_catalog(request(), "npc", "example", 12)
    assert exc.value.status_code == 503
    assert "Configure" in exc.value.detail
    with pytest.raises(HTTPException) as exc:
        editor.search_editor_catalog(request(), "csid", "example", 12)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        editor.search_editor_catalog(request(), "npc", "example", 1000)
    assert exc.value.status_code == 422


def test_picker_cannot_be_used_remotely_or_as_cross_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(editor, "get_dsp_root", lambda: tmp_path)
    for req in (
        request("192.0.2.33"),
        request(headers={"origin": "https://untrusted.example"}),
        request(headers={"x-requested-with": "other"}),
    ):
        with pytest.raises(HTTPException) as exc:
            editor.search_editor_catalog(req, "npc", "some", 10)
        assert exc.value.status_code == 403


def test_shared_scenario_detail_projection_keeps_all_claims_unknown():
    result = editor.validate_editor_spec(synthetic_spec())
    shared = result["reader_view"]
    assert shared["steps"][0]["id"] == "SYNTH-CATALOG-EDITOR-01-S01"
    assert shared["steps"][0]["status"] == "UNKNOWN"
    assert shared["independent_verification"] == "NOT_ESTABLISHED"
    assert shared["mapped_assertion_count"] == 1
    assert result["preview"]["maturity"].startswith("DESIGN_ONLY")
    assert result["execution_enabled"] is False


def test_local_revisioned_save_reopen_and_edit_preserves_candidate_note(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "drafts.sqlite"))
    spec = synthetic_spec()
    source_note = ("[UNVERIFIED catalog candidate] npc: 7001 (Synthetic Sample NPC); "
                   "DSP source: sql/npc_list.sql; source commit UNKNOWN; "
                   "review required before binding or execution")
    spec["steps"][0]["confidence_note"] += "\n" + source_note
    result = editor.validate_editor_spec(spec)
    assert result["reader_view"]["steps"][0]["confidence_note"].endswith(source_note)
    first = save_draft(result["canonical_specification"], 0)
    assert first["revision"] == 1
    restored = get_drafts()[0]["specification"]
    assert restored["steps"][0]["id"] == spec["steps"][0]["id"]
    assert restored["steps"][0]["confidence_note"] == spec["steps"][0]["confidence_note"]
    restored["steps"][0]["title"] = "Updated synthetic observation action"
    second = save_draft(editor.validate_editor_spec(restored)["canonical_specification"], 1)
    assert second["revision"] == 2
    assert get_drafts()[0]["specification"]["steps"][0]["title"] == restored["steps"][0]["title"]
    with pytest.raises(ValueError, match="revision conflict"):
        save_draft(restored, 1)


def test_validation_errors_offer_remediation():
    for failure, expect in [
        ("duplicate step identifier", "stable step ID"),
        ("unknown step assertion reference", "assertion ID"),
        ("unknown step evidence reference", "supported observations"),
        ("published test specifications cannot be overwritten", "Clone"),
        ("drafts must remain design_only", "design-only"),
    ]:
        assert expect in editor._validation_help(failure)


def test_pickers_and_revision_ui_are_in_new_editor_only():
    base = Path(__file__).resolve().parents[1]
    html = (base / "gui/templates/scenario_developer.html").read_text(encoding="utf-8")
    js = (base / "gui/static/scenario_developer.js").read_text(encoding="utf-8")
    for expected in ['id="sd-catalog-kind"', 'id="sd-catalog-query"', 'id="sd-catalog-results"',
                     'id="sd-catalog-step"', 'id="sd-clone"', 'id="sd-revision-state"',
                     'id="sd-source-detail"', '<details>']:
        assert expected in html
    for expected in ["M.attachCandidate(", "M.cloneDraft(", "M.revisionIndicator(",
                     "/scenario-developer/catalog/search", "result.reader_view"]:
        assert expected in js
    for dangerous in ("/builder/launch", "packet_inject", "/itemedit/batch/apply",
                      "send_gm_command"):
        assert dangerous not in js


def test_editor_consumes_context_ref_read_only():
    root = Path(__file__).resolve().parents[1]
    js = (root / "gui/static/scenario_developer.js").read_text(encoding="utf-8")
    html = (root / "gui/templates/scenario_developer.html").read_text(encoding="utf-8")
    assert "context_ref" in js and "contextRefPath" in js and "fromContext" in js
    assert 'id="sd-context-note"' in html
    # the handoff must never save or execute on its own
    body = js[js.index("async function loadContextRef"):js.index("(async()=> {")]
    assert "'POST'" not in body and "/builder/drafts" not in body
