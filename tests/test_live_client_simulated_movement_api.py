"""Same-origin movement preview is reject-only and never reaches the game."""
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router

def test_simulation_does_not_send_game_commands(monkeypatch):
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    origin = {"origin": "http://testserver"}
    assert client.get("/live-client/bridge/movement/capabilities").json()["real_writes_enabled"] is False
    payload = {"client_id": "ashita-a", "zone_id": 235, "dx": 1, "dy": 0,
               "dz": 0, "explicit_consent": True}
    assert client.post("/live-client/bridge/movement/simulate", json=payload).status_code == 403
    assert client.post("/live-client/bridge/movement/simulate", json=payload,
                       headers=origin).status_code == 409
    manager.start()
    try:
        manager.provision("ashita-a")
        monkeypatch.setattr(manager, "status", lambda _: {
            "connected": True,
            "snapshot": SimpleNamespace(position=SimpleNamespace(x=1.0,y=2.0,z=3.0,zone_id=235)),
        })
        result = client.post("/live-client/bridge/movement/simulate", json=payload,
                             headers=origin)
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["executed"] is False
        assert body["kind"] == "reject"
        assert body["reason"] == "writes_not_supported"
        assert body["requested_xyz"] == {"x": 2.0, "y": 2.0, "z": 3.0}
        assert client.post("/live-client/bridge/movement/simulate", json={**payload,"dx":3,"dy":3},
                           headers=origin).status_code == 422
        assert client.post("/live-client/bridge/movement/simulate", json={**payload,"zone_id":236},
                           headers=origin).status_code == 409
    finally:
        manager.stop()
