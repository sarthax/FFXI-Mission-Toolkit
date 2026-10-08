"""Read-only file feed selection and explicit polling API regression."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router


def test_feed_poll_api():
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/"feed.jsonl"
        payload={"schema_version":1,"client_id":"hero","client_version":"fixture",
                 "character":"Hero","adapter":"local-file","observed_at":1,
                 "position":{"zone_id":100,"x":1,"y":2,"z":3,"heading":4},"entities":[]}
        path.write_text(json.dumps(payload)+"\n",encoding="utf-8")
        registry=ReplayRegistry()
        registry.add_feed("hero",FileTelemetryBridge(path,"hero"))
        app=FastAPI()
        app.include_router(create_registry_router(registry))
        browser=TestClient(app)
        endpoint="/live-client/replay/poll-feed?client_id=hero"
        assert browser.post(endpoint).status_code==403
        assert browser.post(endpoint,headers={"origin":"https://wrong.example"}).status_code==403
        response=browser.post(endpoint,headers={"origin":"http://testserver"})
        assert response.status_code==200,response.text
        assert response.json()["accepted"]==1
        assert registry.frame("hero").snapshot.position.x==1
        assert browser.post(endpoint,headers={"origin":"http://testserver"}).json()["accepted"]==0
        assert browser.post("/live-client/replay/poll-feed?client_id=unknown",
                            headers={"origin":"http://testserver"}).status_code==404


def test_feed_settings_and_console_controls():
    root=Path(__file__).resolve().parents[1]
    settings=(root/"gui/templates/settings.html").read_text(encoding="utf-8")
    console=(root/"src/workbench/runtime/live_client/replay_console.py").read_text(encoding="utf-8")
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'value="file_feed"' in settings
    assert 'name="live_client_feed_file"' in settings
    assert 'name="live_client_feed_client"' in settings
    assert 'id="poll"' in console
    assert "FileTelemetryBridge(Path(_feed_path), _feed_client)" in host
