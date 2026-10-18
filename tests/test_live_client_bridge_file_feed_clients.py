"""File-feed clients (e.g. a headless bot) are listed and projected by the bridge endpoints."""
import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router
from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.registry import ReplayRegistry


def frame(client, observed_at, x=481.0):
    return {"schema_version": 1, "client_id": client, "client_version": "headless", "character": "Bot",
            "adapter": "xiheadless-dsp", "observed_at": observed_at,
            "position": {"zone_id": 79, "x": x, "y": -23.0, "z": -500.0, "heading": 0},
            "observation_scope": "bounded_loaded_entities",
            "entities": [{"client_index": 470, "server_entity_id": 17101270, "kind": "unknown", "name": "_272",
                          "position": {"zone_id": 79, "x": 486.8, "y": -23.1, "z": -500.0, "heading": 0}}]}


def make(tmp_path, observed_at):
    path = tmp_path / "bot.jsonl"
    path.write_text(json.dumps(frame("xiheadless-bot", observed_at)) + "\n", encoding="utf-8")
    registry = ReplayRegistry()
    registry.add_feed("xiheadless-bot", FileTelemetryBridge(path, "xiheadless-bot"))
    app = FastAPI()
    app.include_router(create_bridge_management_router(ManagedLiveReceiver(), registry=registry))
    return TestClient(app), path


def test_fresh_file_feed_is_listed_and_projected(tmp_path):
    client, path = make(tmp_path, time.time())
    assert "xiheadless-bot" in client.get("/live-client/bridge/clients").json()["clients"]
    body = client.get("/live-client/bridge/clients/details").json()
    detail = next(d for d in body["details"] if d["id"] == "xiheadless-bot")
    assert detail["source"] == "file_feed" and detail["connected"] is True and detail["character"] == "Bot"
    proj = client.get("/live-client/bridge/projection", params={"client_id": "xiheadless-bot", "zone_id": 79}).json()
    assert proj["visible"] is True and proj["player"]["position"]["x"] == 481.0
    status = client.get("/live-client/bridge/status/xiheadless-bot").json()
    assert status["connected"] is True and status["snapshot"]["adapter"] == "xiheadless-dsp"
    # appended frames are picked up on the next request
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(frame("xiheadless-bot", time.time() + 0.5, x=490.0)) + "\n")
    proj = client.get("/live-client/bridge/projection", params={"client_id": "xiheadless-bot", "zone_id": 79}).json()
    assert proj["player"]["position"]["x"] == 490.0


def test_stale_file_feed_is_not_shown(tmp_path):
    client, _ = make(tmp_path, time.time() - 120)
    proj = client.get("/live-client/bridge/projection", params={"client_id": "xiheadless-bot", "zone_id": 79}).json()
    assert proj["visible"] is False
