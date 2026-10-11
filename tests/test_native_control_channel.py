"""Toolkit-side native control channel: validation, atomic command file, status parsing, API guards."""
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client import native_control as nc
from workbench.runtime.live_client.native_control_api import create_native_control_router


def _status(root, **over):
    kv = {"version": "1", "nonce": "abc", "allow_file_commands": "1", "enabled": "1", "mode": "warp",
          "player_valid": "1", "zone": "98", "zoning": "0", "pos_x": "1.5", "pos_y": "-2.0", "pos_z": "3.0",
          "speed_active": "0", "speed_percent": "100.0", "speed_raw": "5.0", "last_seq": "0",
          "last_id": "", "last_ok": "0", "last_reason": ""}
    kv.update({k: str(v) for k, v in over.items()})
    d = nc.channel_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.txt").write_text("\n".join(f"{k}={v}" for k, v in kv.items()) + "\n")


def test_validation_rejects_bad_input():
    for fields, code in [({"x": "nan", "y": 0, "z": 0}, "invalid_x"),
                         ({"x": 1, "y": float("inf"), "z": 0}, "invalid_y"),
                         ({"x": 1, "y": 2, "z": 99999}, "target_out_of_bounds"),
                         ({"x": 1, "y": 2, "z": 3, "id": "bad id!"}, "invalid_id")]:
        with pytest.raises(nc.NativeControlError) as e:
            nc.build_command("warp_to", fields)
        assert e.value.code == code
    with pytest.raises(nc.NativeControlError):
        nc.build_command("enable", {"mode": "warp"})            # no consent token
    with pytest.raises(nc.NativeControlError):
        nc.build_command("speed", {"value": 10})
    with pytest.raises(nc.NativeControlError):
        nc.build_command("format_disk", {})
    assert nc.build_command("enable", {"mode": "warp", "consent": nc.CONSENT})["mode"] == "warp"


def test_status_parsing_and_staleness(tmp_path):
    assert nc.read_status(tmp_path)["online"] is False
    _status(tmp_path)
    st = nc.read_status(tmp_path)
    assert st["online"] and st["armed"] and st["zone"] == 98
    assert st["position"] == {"x": 1.5, "y": -2.0, "z": 3.0}
    assert st["server_confirmed"] is False and st["scope"] == "client_local"
    old = time.time() - 60
    import os
    os.utime(nc.channel_dir(tmp_path) / "status.txt", (old, old))
    assert nc.read_status(tmp_path)["online"] is False


def test_send_refuses_when_offline_or_channel_disabled(tmp_path):
    with pytest.raises(nc.NativeControlError) as e:
        nc.send_command(tmp_path, "stop")
    assert e.value.code == "plugin_offline"
    _status(tmp_path, allow_file_commands=0)
    with pytest.raises(nc.NativeControlError) as e:
        nc.send_command(tmp_path, "stop")
    assert e.value.code == "channel_disabled"
    assert not (nc.channel_dir(tmp_path) / "command.txt").exists()


def test_send_writes_command_with_nonce_and_reports_outcome(tmp_path):
    _status(tmp_path)

    def fake_plugin():
        path = nc.channel_dir(tmp_path) / "command.txt"
        for _ in range(60):
            if path.exists():
                kv = nc.parse_kv(path.read_text())
                assert kv["nonce"] == "abc" and kv["cmd"] == "warp_to"
                assert (kv["x"], kv["y"], kv["z"]) == ("100.0", "-5.0", "200.0")
                _status(tmp_path, last_seq=kv["seq"], last_id=kv["id"], last_ok=1, last_reason="warp_written")
                return
            time.sleep(0.05)

    t = threading.Thread(target=fake_plugin)
    t.start()
    out = nc.send_command(tmp_path, "warp_to", {"x": 100, "y": -5, "z": 200, "id": "t1"})
    t.join()
    assert out["outcome"]["ok"] and out["outcome"]["reason"] == "warp_written"
    assert out["status"]["server_confirmed"] is False


def test_api_requires_same_origin_and_maps_errors(tmp_path):
    app = FastAPI()
    app.include_router(create_native_control_router(lambda: str(tmp_path)))
    c = TestClient(app, base_url="http://testserver")
    assert c.get("/live-client/native/status").json()["online"] is False
    assert c.post("/live-client/native/stop").status_code == 403           # no Origin header
    ok = {"Origin": "http://testserver"}
    r = c.post("/live-client/native/stop", headers=ok)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "plugin_offline"
    assert c.post("/live-client/native/warp", json={"x": 1, "y": 2, "z": 99999}, headers=ok).status_code == 422
    assert c.post("/live-client/native/arm", json={"mode": "warp", "consent": "yes"}, headers=ok).status_code == 422
    app2 = FastAPI()
    app2.include_router(create_native_control_router(lambda: None))
    assert TestClient(app2).post("/live-client/native/stop", headers=ok).status_code in (403, 409)
