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


def test_dashboard_lists_provisioned_clients_and_displays_health_fields():
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    client = TestClient(app)
    origin = {"origin": "http://testserver"}
    try:
        manager.start()
        manager.provision("ashita-b")
        manager.provision("ashita-a")
        assert client.get("/live-client/bridge/clients").json() == {
            "clients": ["ashita-a", "ashita-b"]
        }
        html = client.get("/live-client/bridge/console")
        assert html.status_code == 200
        for label in ("Live dashboard", "Nearby observed entities", "Technical details"):
            assert label in html.text
    finally:
        manager.stop()


def test_bridge_console_uses_workbench_shell_and_module_tabs():
    from pathlib import Path
    manager = ManagedLiveReceiver()
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    html = TestClient(app).get("/live-client/bridge/console")
    assert html.status_code == 200
    for expected in ("wb-page-frame", "Recordings &amp; replay", "Direct Live Bridge",
                     "aria-current=\"page\"", "Live dashboard", "Download Ashita settings"):
        assert expected in html.text
    assert "<!doctype html><html" not in html.text.lower() or "wb-page-frame" in html.text
    template = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text()
    assert '{% extends "workbench_page.html" %}' in template
    assert "const root='/live-client/bridge/'" in template


def test_operator_setup_feedback_and_safe_live_zone_link():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    assert 'id="bridge-action-message"' in template
    assert 'id="liveZoneLink"' in template
    assert "if(data.connected && Number.isInteger(zone) && zone>=1 && zone<=65535)" in template
    assert "zoneLink.removeAttribute('href')" in template
    assert "reload the ashita addon" in template.lower()
    assert "Existing credentials were revoked." in template


def test_live_bridge_zone_link_preserves_selected_client_and_explicit_opt_in():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    assert "new URLSearchParams({live:'1',client:client(),autozone:'1'})" in template
    assert "if(data.connected && Number.isInteger(zone) && zone>=1 && zone<=65535)" in template
    assert "zoneLink.removeAttribute('href')" in template


def test_bridge_safe_health_report_excludes_private_settings_and_handles_unknown_age():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    assert 'id="bridge-health-hint"' in html
    assert 'id="bridge-copy-health"' in html
    assert "if (!safeHealthReport)" in html
    assert "receiver_running: Boolean(data.running)" in html
    assert "connected: Boolean(data.connected)" in html
    assert "data.age_seconds !== null && data.age_seconds !== undefined" in html
    assert "await navigator.clipboard.writeText(JSON.stringify(safeHealthReport,null,2))" in html
    block = html.split('safeHealthReport = {', 1)[1].split('};', 1)[0]
    assert 'token' not in block and 'session_id' not in block and 'privateConfig' not in block


def test_client_specific_setup_command_and_private_config_invalidation():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    for expected in ("id=\"copyLiveCommand\"", "id=\"liveStartCommand\"",
                     "function clearPrivateConfig()", "function updateLiveCommand()",
                     "clientInput.addEventListener('input'", "provisionedClient !== client()",
                     "clearPrivateConfig();", "provisionedClient=value;",
                     "await navigator.clipboard.writeText('/wblive live start '+id)"):
        assert expected in html
    assert "if(!privateConfig || provisionedClient!==client())return;" in html
