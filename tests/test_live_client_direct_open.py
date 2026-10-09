"""In-page replay import does not require restart or Settings writes."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.setup_api import create_recording_upload_router


def test_open_recording_registers_and_legacy_import_does_not(tmp_path: Path):
    registry = ReplayRegistry()
    app = FastAPI()
    app.include_router(create_recording_upload_router(tmp_path / "recordings", registry))
    client = TestClient(app)
    payload = {"schema_version": 1, "client_id": "test-client-01",
               "client_version": "offline-test", "character": "TestCharacter",
               "adapter": "fixture", "observed_at": 1,
               "position": {"zone_id": 100, "x": 105, "y": 0,
                            "z": 203, "heading": 64}, "entities": []}
    data = (json.dumps(payload) + "\n").encode("utf-8")
    files = {"recording": ("walk.jsonl", data, "application/x-ndjson")}
    headers = {"origin": "http://testserver"}
    old = client.post("/live-client/upload-recording", files=files, headers=headers)
    assert old.status_code == 200, old.text
    assert old.json()["loaded"] is False
    assert registry.client_ids() == ()
    opened = client.post("/live-client/upload-recording?open_session=true",
                         files=files, headers=headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()["loaded"] is True
    session_id = opened.json()["session_id"]
    assert registry.client_ids() == (session_id,)
    assert registry.frame(session_id).snapshot.position.x == 105
    again = client.post("/live-client/upload-recording?open_session=true",
                        files=files, headers=headers)
    assert again.status_code == 200
    assert again.json()["session_id"] != session_id
    assert client.post("/live-client/upload-recording?open_session=true",
                       files=files).status_code == 403


def test_console_has_direct_open_ui():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/workbench/runtime/live_client/replay_console.py").read_text(encoding="utf-8")
    assert 'id="open-recording"' in source
    assert "open_session:" in source
