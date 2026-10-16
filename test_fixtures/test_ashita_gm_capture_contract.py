"""GM chat capture is strictly opt-in and uses the existing bounded capture lane."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "addons/workbench_live"


def test_gm_capture_is_opt_in_and_filtered():
    src = (ROOT / "workbench_gm_capture.lua").read_text(encoding="utf-8")
    assert "active = false" in src
    assert "armed_until = opts.now() + 20" in src
    assert "current action ID is %d+" in src
    assert "if not id then return end" in src
    assert "stop()" in src
    assert "opts.send(json)" in src


def test_incoming_text_wired_without_chat_mutation():
    src = (ROOT / "workbench_live_ashita.lua").read_text(encoding="utf-8")
    assert "register('text_in', 'workbench_live_gm_text'" in src
    assert "gm_capture.on_text(e)" in src
    assert "gm_capture.arm()" in src
    assert "gm_capture.stop()" in src
    assert "e.blocked = true" in src  # existing /wblive command handler only


def test_bridge_uses_dedicated_capture_lane():
    src = (ROOT / "workbench_bridge.lua").read_text(encoding="utf-8")
    assert "return send_event(client_id, json, 'capture', 'capture_event')" in src
    assert "client_id=function() return source end" in src
