from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router


def test_capability_probe_is_local_fresh_and_never_executes_game_writes(monkeypatch):
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    payload = {"client_id": "ashita-a"}
    local = {"origin": "http://testserver"}
    assert client.post("/live-client/bridge/control/probe", json=payload).status_code == 403
    assert client.post("/live-client/bridge/control/probe", json=payload, headers=local).status_code == 409
    manager.start()
    try:
        manager.provision("ashita-a")
        monkeypatch.setattr(manager, "status", lambda _: {"connected": True, "snapshot": SimpleNamespace()})
        response = client.post("/live-client/bridge/control/probe", json=payload, headers=local)
        assert response.status_code == 200, response.text
        assert response.json()["writes_enabled"] is False
        assert response.json()["state"] == "queued"
        assert client.get("/live-client/bridge/control/probe/ashita-a").json()["state"] == "queued"
        assert client.post("/live-client/bridge/control/probe", json=payload, headers=local).status_code == 409
        manager.reset_credentials("ashita-a")
        assert client.get("/live-client/bridge/control/probe/ashita-a").json()["state"] == "cancelled"
    finally:
        manager.stop()
