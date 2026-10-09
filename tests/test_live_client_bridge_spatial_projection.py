"""Live Bridge spatial projection shares the existing viewer contract."""
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_live_client_bridge_managed import push
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router


def test_projection_requires_fresh_matching_zone_and_client():
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    with manager:
        conf = manager.provision("ashita-a")
        path = "/live-client/bridge/projection"
        params = {"client_id": "ashita-a", "zone_id": 235}
        assert client.get(path, params=params).json()["visible"] is False
        push(conf, 100)
        deadline = time.monotonic() + 4
        while not manager.status("ashita-a")["connected"] and time.monotonic() < deadline:
            time.sleep(.02)
        result = client.get(path, params=params)
        assert result.status_code == 200
        projection = result.json()
        assert projection["visible"] is True
        assert projection["player"]["character"] == "Hero"
        assert projection["zone_id"] == 235
        assert projection["player"]["position"]["x"] == 100
        assert client.get(path, params={"client_id": "ashita-a", "zone_id": 107}).json()["visible"] is False
        assert client.get(path, params={"client_id": "ashita-b", "zone_id": 235}).json()["visible"] is False
        assert client.get(path, params={**params, "instance_hint": "other"}).json()["visible"] is False


def test_projection_does_not_render_last_known_coordinates_when_disconnected():
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    with manager:
        conf = manager.provision("ashita-a")
        push(conf, 100)
        deadline = time.monotonic() + 4
        while not manager.status("ashita-a")["connected"] and time.monotonic() < deadline:
            time.sleep(.02)
        manager._last_received["ashita-a"] = time.monotonic() - 10
        result = client.get("/live-client/bridge/projection", params={"client_id": "ashita-a", "zone_id": 235}).json()
        assert result == {"visible": False, "player": None, "entities": [],
                          "reason": "receiver_disconnected_or_stale"}
