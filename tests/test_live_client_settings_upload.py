"""Live Client browser upload integration tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.setup_api import create_recording_upload_router


def test_browser_recording_upload():
    with TemporaryDirectory() as tmp:
        app = FastAPI()
        app.include_router(create_recording_upload_router(Path(tmp)))
        client = TestClient(app)
        data = {"schema_version": 1, "client_id": "demo", "client_version": "fixture",
                "character": "Hero", "adapter": "offline", "observed_at": 1,
                "position": {"zone_id": 100, "x": 0, "y": 0, "z": 0, "heading": 0},
                "entities": []}
        contents = (json.dumps(data) + "\n").encode()
        endpoint = "/live-client/upload-recording"
        files = {"recording": ("session.jsonl", contents, "application/x-ndjson")}
        assert client.post(endpoint, files=files).status_code == 403
        headers = {"origin": "http://testserver"}
        response = client.post(endpoint, files=files, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["client_id"] == "demo"
        assert result["frames"] == 1
        assert Path(result["path"]).parent == Path(tmp)
        assert Path(result["path"]).read_bytes() == contents
        assert client.post(endpoint, files={"recording": ("bad.txt", contents)},
                           headers=headers).status_code == 422
        assert client.post(endpoint, files={"recording": ("bad.jsonl", b"broken")},
                           headers=headers).status_code == 422
        assert len(list(Path(tmp).glob("*.jsonl"))) == 1


def test_settings_browse_controls_and_ignore():
    root = Path(__file__).resolve().parents[1]
    html = (root / "gui/templates/settings.html").read_text(encoding="utf-8")
    assert 'id="liveClientUploadFile"' in html
    assert 'id="liveClientUpload"' in html
    assert "live-client/upload-recording" in html
    assert "data/live_client_recordings/" in (root / ".gitignore").read_text(encoding="utf-8")
