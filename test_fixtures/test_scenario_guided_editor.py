"""Synthetic-only tests for #1261 Guided Scenario Developer.

No client, runner, GM, server SQL or DB connection; tmp_path draft SQLite only.
"""
import copy
from pathlib import Path

import pytest
from fastapi import HTTPException

from workbench.server_admin.feature_testing.test_specifications import specification
from workbench.server_admin.feature_testing.spec_drafts import save_draft, get_drafts
from workbench.server_admin.scenario_authoring.editor_router import (
    editor_options, validate_editor_spec, _local_origin,
)


def synthetic_draft():
    spec = copy.deepcopy(specification("moghancement", "MOG-09"))
    assert spec.get("steps"), "Run against draft PR #1263 canonical BDD contract"
    spec["case_id"] = "SYNTH-MOG-09-EDITOR"
    spec["runner"] = "unassigned"
    spec["execution_status"] = "design_only"
    spec["authoring"] = {
        "state": "draft", "execution_policy": "read_only",
        "evidence_provenance": "synthetic_only",
        "blocking_gaps": ["UNKNOWN installed furniture layout and readback"],
        "review_required": True,
    }
    return spec


def test_six_steps_can_be_previewed_but_never_authenticated():
    spec = synthetic_draft()
    result = validate_editor_spec(spec)
    view = result["preview"]
    assert result["canonical_specification"] == spec
    assert result["execution_enabled"] is False
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert view["maturity"].startswith("DESIGN_ONLY")
    assert view["recorded_verdict"] is view["recalculated_verdict"] is None
    assert [x["id"] for x in view["steps"]] == [x["id"] for x in spec["steps"]]
    assert len(view["steps"]) == len(spec["assertions"]) == 6
    assert all(x["verdict"] == "UNKNOWN" for x in view["steps"])
    assert all(x["observed"].startswith("UNKNOWN") for x in view["steps"])
    assert "UNKNOWN installed furniture" in result["warnings"][0]


def test_reordering_and_editing_preserves_all_step_ids_and_other_fields():
    spec = synthetic_draft()
    before = copy.deepcopy(spec)
    item = spec["steps"].pop(2)
    spec["steps"].insert(0, item)
    spec["steps"][0]["expected"] = "UNKNOWN — source oracle needs reconfirmation"
    spec["purpose"] = "Synthetic revised scenario"
    result = validate_editor_spec(spec)
    assert result["preview"]["steps"][0]["id"] == item["id"]
    assert sorted(s["id"] for s in result["canonical_specification"]["steps"]) == sorted(
        s["id"] for s in before["steps"]
    )
    assert result["canonical_specification"]["assertions"] == before["assertions"]
    assert result["canonical_specification"]["preconditions"] == before["preconditions"]
    assert result["preview"]["unresolved_expected_steps"] == [item["id"]]


@pytest.mark.parametrize("mutate,expected", [
    (lambda s: s["steps"][1].update(id=s["steps"][0]["id"]), "duplicate step"),
    (lambda s: s["steps"][0].update(assertion_ids=["invented_assertion"]), "unknown step assertion"),
    (lambda s: s["steps"][0].update(evidence_refs=["invented_observation"]), "unknown step evidence"),
    (lambda s: s["assertions"][1].update(id=s["assertions"][0]["id"]), "duplicate"),
    (lambda s: s.update(runner="xiheadless_observation_v1"), "design_only"),
    (lambda s: s.update(execution_status="verified_runner"), "design_only"),
    (lambda s: s["authoring"].update(review_required=False), "review cannot be waived"),
    (lambda s: s["authoring"].update(execution_policy="mutating"), "read-only"),
    (lambda s: s["authoring"].update(state="reviewed"), "cannot claim reviewed"),
    (lambda s: s["steps"][0].update(intent="send_gm"), "mutating step intent"),
    (lambda s: s.update(unsafe_dispatch=True), "unexpected"),
])
def test_canonical_contract_and_safety_fail_closed(mutate, expected):
    spec = synthetic_draft()
    mutate(spec)
    with pytest.raises(ValueError, match=expected):
        validate_editor_spec(spec)


def test_save_then_edit_roundtrips_canonical_bdd_without_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "synthetic_drafts.sqlite"))
    spec = synthetic_draft()
    validated = validate_editor_spec(spec)["canonical_specification"]
    first = save_draft(validated, 0)
    assert first["revision"] == 1
    assert first["execution_enabled"] is False
    loaded = get_drafts()
    assert loaded[0]["specification"] == spec
    loaded_spec = loaded[0]["specification"]
    loaded_spec["steps"][0]["title"] = "Synthetic revised step title"
    loaded_spec["behavior"]["then"].append("UNKNOWN — pending independent oracle")
    second = save_draft(validate_editor_spec(loaded_spec)["canonical_specification"], 1)
    assert second["revision"] == 2
    assert get_drafts()[0]["specification"] == loaded_spec
    with pytest.raises(ValueError, match="revision conflict"):
        save_draft(loaded_spec, 1)


def test_catalog_option_names_are_canonical_not_unverified_client_ids():
    options = editor_options()
    assert options["catalog_status"] == "UNRESOLVED"
    assert options["execution_enabled"] is False
    assert "client_bag" in options["observations"]
    assert "nonempty" in options["operations"]
    assert any(f["id"] == "moghancement" for f in options["features"])
    assert all("id" in feature and "name" in feature for feature in options["features"])


def test_page_is_separate_from_feature_testing_viewer_and_has_no_dispatch():
    root = Path(__file__).resolve().parents[1]
    page = (root / "gui/templates/scenario_developer.html").read_text(encoding="utf-8")
    script = (root / "gui/static/scenario_developer.js").read_text(encoding="utf-8")
    host = (root / "src/workbench/app/host.py").read_text(encoding="utf-8")
    assert 'id="sd-guided"' in page and 'id="sd-advanced"' in page
    assert 'id="sd-steps"' in page and 'id="sd-add-step"' in page
    assert 'id="sd-preview"' in page and 'id="sd-token"' in page
    assert "/scenario-developer/validate" in script
    assert "/feature-testing/builder/drafts" in script
    assert "app.include_router(scenario_developer_router)" in host
    for unsafe in ("/builder/launch", "send_gm_command", "/itemedit/batch/apply",
                   "packet_inject", "exec(", "fetch('http"):
        assert unsafe not in script


def test_local_origin_required_even_for_nonmutating_validation():
    from starlette.requests import Request
    scope = {
        "type": "http", "method": "POST", "path": "/scenario-developer/validate",
        "scheme": "http", "server": ("127.0.0.1", 8420),
        "client": ("192.0.2.12", 1234),
        "headers": [(b"content-type", b"application/json")],
    }
    with pytest.raises(HTTPException) as exc:
        _local_origin(Request(scope))
    assert exc.value.status_code == 403
    scope["client"] = ("127.0.0.1", 1234)
    scope["headers"] += [(b"origin", b"https://malicious.example")]
    with pytest.raises(HTTPException) as exc:
        _local_origin(Request(scope))
    assert exc.value.status_code == 403


def test_host_serves_editor_and_canonical_validation(monkeypatch):
    from fastapi.testclient import TestClient
    host = pytest.importorskip("workbench.app.host", exc_type=Exception)
    client = TestClient(host.app, client=("127.0.0.1", 50000))
    response = client.get("/scenario-developer")
    assert response.status_code == 200
    assert "Guided Scenario Developer" in response.text
    valid = client.post("/scenario-developer/validate",
                        json={"specification": synthetic_draft()})
    assert valid.status_code == 200, valid.text
    assert valid.json()["preview"]["execution_enabled"] is False
    bad = synthetic_draft()
    bad["steps"][0]["assertion_ids"] = ["missing_assertion"]
    response = client.post("/scenario-developer/validate", json={"specification": bad})
    assert response.status_code == 422
    # Existing persistence endpoint must continue requiring operator auth.
    response = client.post("/feature-testing/builder/drafts",
                           json={"specification": synthetic_draft(), "expected_revision": 0})
    assert response.status_code == 403


def test_validation_workspace_exposes_design_only_editor_without_viewer_overlap():
    from workbench.gui_shell import WORKSPACES
    validation = next(w for w in WORKSPACES if w["name"] == "Validation")
    entries = [x for x in validation["sections"] if x["href"] == "/scenario-developer"]
    assert len(entries) == 1
    assert "design only" in entries[0]["label"].lower()
    assert not any("/feature-testing" in x["href"] for x in entries)
