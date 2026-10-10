"""One-step receiver start: persisted port/credentials, settings written to Ashita folder."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_peers import PeerIdentity


def _client(manager):
    app = FastAPI()
    app.include_router(create_bridge_management_router(manager))
    return TestClient(app, base_url="http://testserver")


def _ashita(tmp_path):
    root = tmp_path / "Ashita"
    (root / "addons").mkdir(parents=True)
    return root


def test_restart_reuses_port_and_credentials(tmp_path):
    state = tmp_path / "state.json"
    first = ManagedLiveReceiver(state_path=state)
    first.start()
    creds = first.provision("ashita-a", reuse=True)
    first.stop()
    second = ManagedLiveReceiver(state_path=state)
    second.start()
    try:
        again = second.provision("ashita-a", reuse=True)
        assert again == creds  # same port, session, generation, token
        assert second.peers.authenticate(
            PeerIdentity("ashita-a", creds["session_id"], creds["generation"]), creds["token"])
        regenerated = second.provision("ashita-a", reuse=False)
        assert regenerated["token"] != creds["token"]
    finally:
        second.stop()


def test_without_state_path_nothing_is_persisted(tmp_path):
    m = ManagedLiveReceiver()
    m.start()
    try:
        a = m.provision("ashita-a", reuse=True)
        b = m.provision("ashita-a", reuse=True)
        assert a["token"] != b["token"]
    finally:
        m.stop()


def test_quick_start_is_one_step_and_writes_settings(tmp_path):
    manager = ManagedLiveReceiver(state_path=tmp_path / "state.json")
    http = _client(manager)
    root = _ashita(tmp_path)
    try:
        r = http.post("/live-client/bridge/quick-start", headers={"origin": "http://testserver"},
                      json={"client_id": "ashita-a", "ashita_root": str(root)})
        body = r.json()
        assert r.status_code == 200 and body["settings_written"] and body["settings_changed"]
        assert "settings_lua" not in body and "token" not in str(body)
        written = (root / "addons" / "workbench_live" / "workbench_bridge_settings.lua").read_text()
        assert f"port = {body['port']}" in written
        # Second click: idempotent, file unchanged, root remembered without being resent.
        r2 = http.post("/live-client/bridge/quick-start", headers={"origin": "http://testserver"},
                       json={"client_id": "ashita-a"}).json()
        assert r2["settings_written"] and not r2["settings_changed"]
    finally:
        manager.stop()


def test_quick_start_without_folder_returns_manual_download(tmp_path):
    manager = ManagedLiveReceiver(state_path=tmp_path / "state.json")
    http = _client(manager)
    try:
        body = http.post("/live-client/bridge/quick-start", headers={"origin": "http://testserver"},
                         json={"client_id": "ashita-a"}).json()
        assert not body["settings_written"] and "return {" in body["settings_lua"]
    finally:
        manager.stop()


def test_quick_start_requires_same_origin(tmp_path):
    manager = ManagedLiveReceiver(state_path=tmp_path / "state.json")
    r = _client(manager).post("/live-client/bridge/quick-start", json={"client_id": "ashita-a"})
    assert r.status_code == 403
