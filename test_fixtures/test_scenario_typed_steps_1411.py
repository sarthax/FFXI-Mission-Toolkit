"""#1411 typed step builder: the two local-only routes and the page wiring. Offline, synthetic values only."""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.server_admin.feature_testing import typed_action_library as lib
from workbench.server_admin.scenario_authoring import editor_router

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ("127.0.0.1", 5000)


def client(host=LOCAL):
    app = FastAPI()
    app.include_router(editor_router.router)
    return TestClient(app, client=host)


def post(c, body, **kwargs):
    return c.post("/scenario-developer/typed-step", json=body, **kwargs)


def test_library_route_returns_the_reviewed_registry():
    response = client().get("/scenario-developer/typed-library")
    assert response.status_code == 200
    assert response.json() == json.loads(json.dumps(lib.export_registry()))
    assert response.json()["headless_wire_contract_approved"] is False


def test_valid_step_is_built_as_a_nonexecutable_native_draft():
    response = post(client(), {"template_id": "navigate_near", "action_value": [1.5, 2.5], "expectation_value": 4.2})
    assert response.status_code == 200
    step = response.json()
    assert step["do"] == {"walk_to": [1.5, 2.5]} and step["expect"] == {"x_near": 4.2}
    assert (step["oracle_status"], step["verdict"], step["execution_enabled"]) == ("UNAPPROVED", "UNKNOWN", False)


@pytest.mark.parametrize("body,part,fragment", [
    ({"template_id": "talk_to_npc", "action_value": -1, "expectation_value": True}, "action", "npc_id"),
    ({"template_id": "talk_to_npc", "action_value": 5, "expectation_value": "yes"}, "expectation", "event_active"),
    ({"template_id": "recover_hp", "action_value": 0, "expectation_value": 1}, "action", "1..100"),
    ({"template_id": "navigate_near", "action_value": [1, 2, 3, 4], "expectation_value": 1}, "action", "coordinates"),
    ({"template_id": "navigate_near", "action_value": [1.0, 2.0], "expectation_value": None}, "expectation", "x_near"),
    ({"template_id": "talk_to_npc", "action_value": True, "expectation_value": True}, "action", "npc_id"),
    ({"template_id": "read_inventory", "action_value": 1, "expectation_value": 1}, "template", "Toolkit readback"),
    ({"template_id": "warp_target", "action_value": 1, "expectation_value": 1}, "template", "unknown template"),
])
def test_bad_values_are_rejected_with_the_part_and_a_reason(body, part, fragment):
    response = post(client(), body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["part"] == part and fragment in detail["message"]


def test_non_finite_numbers_in_the_request_body_are_rejected():
    c = client()
    for raw in ('{"template_id":"navigate_near","action_value":[NaN,2],"expectation_value":1}',
                '{"template_id":"navigate_near","action_value":[1,2],"expectation_value":Infinity}'):
        response = c.post("/scenario-developer/typed-step", content=raw, headers={"content-type": "application/json"})
        assert response.status_code == 422, raw


def test_the_builder_post_rejects_non_json_body():
    body = {"template_id": "talk_to_npc", "action_value": 1, "expectation_value": True}
    response = client().post("/scenario-developer/typed-step", content=json.dumps(body),
                             headers={"content-type": "text/plain"})
    assert response.status_code in (415, 422)  # refused before any step is built (same ordering as /validate)
    assert "do" not in response.text


# Security and side-effect contracts are shared, but each route is still
# exercised independently. Param ids keep failed endpoints obvious.
BUILDER_BODY = {"template_id": "talk_to_npc", "action_value": 1, "expectation_value": True}
REVIEW_STEPS = [{"name": "go", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}}]


@pytest.mark.parametrize("operation", [
    pytest.param(lambda c, **kw: post(c, BUILDER_BODY, **kw), id="typed-step"),
    pytest.param(lambda c, **kw: review_post(c, REVIEW_STEPS, **kw), id="typed-import"),
])
def test_typed_writes_reject_nonlocal_and_cross_origin(operation):
    assert operation(client(("203.0.113.9", 5000))).status_code == 403
    assert operation(client(), headers={"origin": "http://evil.example"}).status_code == 403


@pytest.mark.parametrize("operation", [
    pytest.param(lambda c: c.get("/scenario-developer/typed-library"), id="typed-library"),
    pytest.param(lambda c: post(c, BUILDER_BODY), id="typed-step"),
    pytest.param(lambda c: review_post(c, REVIEW_STEPS), id="typed-import"),
])
def test_typed_routes_do_not_spawn_processes_or_open_database(monkeypatch, operation):
    import sqlite3, subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no process")))
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no database")))
    assert operation(client()).status_code == 200


def test_page_wires_the_builder_without_touching_the_canonical_editor():
    html = (ROOT / "gui" / "templates" / "scenario_developer.html").read_text(encoding="utf-8")
    assert 'id="sd-typed-root"' in html and "/static/scenario_typed_steps.js" in html
    assert html.index("/static/scenario_developer.js") < html.index("/static/scenario_typed_steps.js")
    # The host provides the shell globals; supply neutral stand-ins so the real template renders.
    editor_router.templates.env.globals.setdefault("current_theme", lambda *a, **k: "dark")
    editor_router.templates.env.globals.setdefault("shell_context", lambda *a, **k: {})
    page = client().get("/scenario-developer")
    assert page.status_code == 200
    assert 'id="sd-typed-root"' in page.text and "/static/scenario_typed_steps.js" in page.text


# --- #1411 pickers: the catalog search route returns what the UI relies on ---------------------

@pytest.fixture()
def fake_dsp(tmp_path, monkeypatch):
    (tmp_path / "sql").mkdir()
    (tmp_path / "sql" / "npc_list.sql").write_text(
        "INSERT INTO `npc_list` VALUES (17719298,'synth_guard','Synthetic Guard',0,0,0);\n"
        "INSERT INTO `npc_list` VALUES (17719300,'dup_a','Duplicate Id Person',0,0,0);\n"
        "INSERT INTO `npc_list` VALUES (17719300,'dup_b','Duplicate Id Person',0,0,0);\n", encoding="utf-8")
    (tmp_path / "sql" / "zone_settings.sql").write_text(
        "INSERT INTO `zone_settings` VALUES (231,1,'synth_zone_a',1,'Synthetic Zone One',0);\n", encoding="utf-8")
    monkeypatch.setattr(editor_router, "get_dsp_root", lambda: str(tmp_path))
    return tmp_path


def search(c, kind, query):
    return c.get(f"/scenario-developer/catalog/search?kind={kind}&query={query}", headers={"x-requested-with": "toolkit-ui"})


def usable(candidate, kind):  # mirrors usableCandidate() in scenario_typed_steps.js
    return (isinstance(candidate, dict) and candidate.get("kind") == kind and type(candidate.get("id")) is int
            and candidate["id"] >= 0 and isinstance(candidate.get("name"), str) and candidate["name"].strip() != ""
            and isinstance(candidate.get("source_path"), str))


def test_picker_search_returns_unverified_candidates_in_the_shape_the_ui_uses(fake_dsp):
    for kind, query, expected_id, source in (("npc", "guard", 17719298, "sql/npc_list.sql"),
                                              ("zone", "synthetic", 231, "sql/zone_settings.sql")):
        body = search(client(), kind, query).json()
        assert body["binding_verified"] is False and body["execution_enabled"] is False
        assert body["operator_review_required"] is True
        assert body["completeness"] == "bounded_catalog_query_not_full_inventory"
        [candidate] = body["choices"]
        assert usable(candidate, kind) and candidate["id"] == expected_id and candidate["source_path"] == source
        assert candidate["identity_status"] == "unreconciled_source_candidate"
        assert candidate["binding_verified"] is False and candidate["execution_enabled"] is False


def test_picker_search_flags_duplicate_ids_and_does_not_hide_them(fake_dsp):
    choices = search(client(), "npc", "person").json()["choices"]
    assert len(choices) == 2 and all(c["id"] == 17719300 and c["duplicate_id_in_results"] for c in choices)


def test_picker_search_with_no_source_is_unavailable_not_empty(monkeypatch):
    monkeypatch.setattr(editor_router, "get_dsp_root", lambda: "")
    response = search(client(), "npc", "guard")
    assert response.status_code == 503 and "No DSP source checkout configured" in response.json()["detail"]


def test_picker_search_is_local_only_and_needs_the_editor_header(fake_dsp):
    assert client().get("/scenario-developer/catalog/search?kind=npc&query=guard").status_code == 403
    assert search(client(("203.0.113.9", 5000)), "npc", "guard").status_code == 403
    assert search(client(), "npc", "x" * 65).status_code == 422


# --- native import review route ---------------------------------------------------------------

def review_post(c, steps, **kwargs):
    return c.post("/scenario-developer/typed-import", json={"steps": steps}, **kwargs)


def test_import_review_route_reports_each_step_and_accepts_nothing():
    steps = [{"name": "go", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}},
             {"name": "bad", "do": {"talk_npc": -1}, "expect": {"event_active": True}},
             {"name": "odd", "do": {"dance": 1}, "expect": {"zone": 1}}]
    response = review_post(client(), steps)
    assert response.status_code == 200
    body = response.json()
    assert body["source_trust"] == "UNREVIEWED_EXTERNAL_INPUT"
    assert [r["status"] for r in body["steps"]] == ["SUPPORTED", "INVALID", "UNSUPPORTED"]
    assert body["counts"] == {"SUPPORTED": 1, "UNSUPPORTED": 1, "INVALID": 1}
    assert body["steps"][0]["step"]["do"] == {"walk_to": [1, 2]} and body["steps"][1]["step"] is None


@pytest.mark.parametrize("steps", [None, {}, "x", [], [None] * 101])
def test_import_review_route_rejects_a_bad_scenario_with_a_message(steps):
    response = review_post(client(), steps)
    assert response.status_code == 422
    assert "array of 1 to 100 steps" in response.json()["detail"]["message"]


def test_import_review_route_rejects_oversized_payload():
    big = [{"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "pad": "x" * 40000}]
    assert review_post(client(), big).status_code == 413
