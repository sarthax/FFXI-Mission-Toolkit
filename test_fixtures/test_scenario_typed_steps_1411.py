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


def test_the_builder_post_is_local_only_json_only_and_same_origin():
    body = {"template_id": "talk_to_npc", "action_value": 1, "expectation_value": True}
    assert post(client(("203.0.113.9", 5000)), body).status_code == 403          # not a local client
    assert post(client(), body, headers={"origin": "http://evil.example"}).status_code == 403
    response = client().post("/scenario-developer/typed-step", content=json.dumps(body),
                             headers={"content-type": "text/plain"})
    assert response.status_code in (415, 422)  # refused before any step is built (same ordering as /validate)
    assert "do" not in response.text


def test_no_process_or_database_is_used_by_the_routes(monkeypatch):
    import sqlite3, subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no process")))
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no database")))
    c = client()
    assert c.get("/scenario-developer/typed-library").status_code == 200
    assert post(c, {"template_id": "talk_to_npc", "action_value": 1, "expectation_value": True}).status_code == 200


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
