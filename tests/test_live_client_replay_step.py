"""Explicit offline replay step endpoint and browser contract."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay_console import create_replay_console_router
from workbench.runtime.live_client.replay import RecordedTelemetryReplay


def _frame(t):
    return {"schema_version": 1, "client_id": "demo", "client_version": "fixture",
            "character": "Hero", "adapter": "offline", "observed_at": t,
            "position": {"zone_id": 100, "x": t, "y": 0, "z": 0, "heading": 0},
            "entities": []}


def test_step_is_same_origin_and_stops_at_end():
    registry = ReplayRegistry()
    registry.add("demo", RecordedTelemetryReplay("demo", [_frame(1), _frame(2)]))
    app = FastAPI()
    app.include_router(create_registry_router(registry))
    app.include_router(create_replay_console_router())
    client = TestClient(app)
    endpoint = "/live-client/replay/advance?client_id=demo"
    assert client.post(endpoint).status_code == 403
    assert client.post(endpoint, headers={"origin": "https://other.test"}).status_code == 403
    assert registry.frame("demo") is None
    same_origin = {"origin": "http://testserver"}
    first = client.post(endpoint, headers=same_origin)
    assert first.status_code == 200
    assert first.json()["observed_at"] == 1
    assert client.post(endpoint, headers=same_origin).json()["observed_at"] == 2
    assert client.post(endpoint, headers=same_origin).status_code == 409
    assert registry.frame("demo").snapshot.observed_at == 2
    assert client.post("/live-client/replay/advance?client_id=missing",
                       headers=same_origin).status_code == 404
    html = client.get("/live-client/replay/console").text
    assert 'id="step"' in html
    assert "method:'POST'" in html
