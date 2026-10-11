"""Direct Live sampling rate behavior is bounded and subsecond capable."""
from pathlib import Path
import pytest
from workbench.runtime.live_client.bridge_settings_file import render_settings_lua

ADDON = Path(__file__).resolve().parents[1] / "addons/workbench_live"


def test_generated_bridge_settings_rate_is_bounded():
    creds = dict(port=8421, session_id="session", generation="generation", token="a"*32)
    for hz in (1, 5, 10, 20):
        assert f"sample_hz = {hz}" in render_settings_lua(creds, hz)
    for invalid in (0, 2, 21, True, 1.5):
        with pytest.raises(ValueError):
            render_settings_lua(creds, invalid)


def test_subsecond_live_sampler_and_no_duplicate_timestamps():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local now, frames = 100.0, {}
        local direct = require('workbench_live_direct').new({
            now=function() return now end, sample_hz=10,
            capture=function(id, t)
                return {client_id=id, source_identity='test:Hero', character='Hero',
                    schema_version=1, client_version='test', adapter='test',
                    observed_at=t, position={zone_id=235,x=t,y=2,z=3,heading=0}, entities={}}
            end,
            start_bridge=function() return true end,
            stop_bridge=function() end,
            send=function(id, wire) table.insert(frames, wire); return true end,
        })
        assert(direct.start('ashita-a'))
        direct.sample()
        now=100.05; direct.sample()
        now=100.10; direct.sample()
        now=100.20; direct.sample()
        assert(#frames==3)
        assert(frames[1]:find('"observed_at":100', 1, true))
        assert(frames[2]:find('"observed_at":100.1', 1, true))
        now=99; direct.sample()
        assert(not direct.active())
    """)


def test_console_and_viewer_refresh_controls():
    root=Path(__file__).resolve().parents[1]
    console=(root/"gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    viewer=(root/"gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert 'id="live-sample-hz"' in console
    assert "sample_hz:Number(document.getElementById('live-sample-hz').value)" in console
    assert 'id="ashita-live-refresh"' in viewer
    assert "scheduleLivePolling()" in viewer
