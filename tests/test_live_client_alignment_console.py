"""Read-only bridge alignment console and endpoint guards."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router
from test_live_client_alignment import sample


def test_local_same_origin_alignment_validation_and_rejection():
    app = FastAPI()
    app.include_router(create_bridge_management_router(ManagedLiveReceiver()))
    client = TestClient(app)
    endpoint = "/live-client/bridge/alignment/validate"
    headers = {"origin": "http://testserver"}
    response = client.post(endpoint, headers=headers, json=sample())
    assert response.status_code == 200
    assert response.json()["raw_distance"] == 5
    assert response.json()["calibrated"] is False
    assert response.json()["write_safe"] is False
    assert client.post(endpoint, json=sample()).status_code == 403
    mismatched = sample()
    mismatched["points"][1]["zone_id"] = 99
    assert client.post(endpoint, headers=headers, json=mismatched).status_code == 422


def test_console_includes_readonly_alignment_interface():
    html = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    for token in ('id="alignment-json"', 'id="alignment-validate"', 'id="alignment-clear"',
                  "alignment/validate", "JSON.parse(alignmentInput.value)", "alignmentResult.textContent"):
        assert token in html
