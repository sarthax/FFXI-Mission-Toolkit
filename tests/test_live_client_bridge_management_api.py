"""Bridge management routes stay opt-in and prohibit cross-origin mutations."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router


def test_same_origin_start_provision_status_stop_without_log_files():
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    origin = {"origin": "http://testserver"}
    try:
        assert client.post("/live-client/bridge/start").status_code == 403
        assert client.post("/live-client/bridge/start", headers=origin).status_code == 200
        config = client.post("/live-client/bridge/provision",
                             json={"client_id": "ashita-a"}, headers=origin)
        assert config.status_code == 200
        assert len(config.json()["token"]) >= 32
        status = client.get("/live-client/bridge/status/ashita-a")
        assert status.status_code == 200
        assert status.json()["running"] is True
        assert status.json()["snapshot"] is None
        assert client.post("/live-client/bridge/stop", headers=origin).json() == {"running": False}
    finally:
        manager.stop()


def test_bad_client_and_cross_origin_provision_rejected():
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    assert client.post("/live-client/bridge/provision",
                       json={"client_id": "ashita-a"},
                       headers={"origin": "https://evil.example"}).status_code == 403
    assert client.get("/live-client/bridge/status/invalid%20client").status_code == 422
    assert client.post("/live-client/bridge/provision",
                       json={"client_id": "bad id"},
                       headers={"origin": "http://testserver"}).status_code == 422
