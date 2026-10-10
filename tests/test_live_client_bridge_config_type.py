"""Regression for Lua require() returning true when settings do not return a table."""
from pathlib import Path
import pytest

ADDON = Path(__file__).resolve().parents[1] / "addons" / "workbench_live"


def test_boolean_bridge_config_is_disabled_not_crash():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("""
        package.path = addon_dir .. '?.lua;' .. package.path
        local bridge = require('workbench_bridge').new(true)
        assert(bridge.start('ashita-a') == false)
        assert(bridge.active() == false)
        local missing = require('workbench_bridge').new(false)
        assert(missing.start('ashita-a') == false)
    """)


def test_entry_point_normalizes_lua_require_sentinel():
    entry = (ADDON / "workbench_live_ashita.lua").read_text(encoding="utf-8")
    assert "type(bridge_config) == 'table'" in entry
    assert "bridge_options = {enabled=false}" in entry
    assert "require('workbench_bridge').new(bridge_options," in entry


def _runtime():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute("package.path = addon_dir .. '?.lua;' .. package.path")
    return lua


_GOOD = """{enabled=true, host='127.0.0.1', port=60568, session_id='s1', generation='g1',
  token='%s', connect=%s}"""
_TOKEN = "A" * 43


def _start(lua, options, load_error="nil"):
    return lua.execute("""
        local b = require('workbench_bridge').new(%s, nil, %s)
        local ok, why = b.start('ashita-a')
        return tostring(ok) .. '|' .. tostring(why)
    """ % (options, load_error))


def test_start_reports_specific_reasons_without_secrets():
    lua = _runtime()
    ok_conn = "function() return {close=function() end} end"
    assert _start(lua, _GOOD % (_TOKEN, ok_conn)).startswith("true")
    assert "receiver unreachable: connection refused" in _start(
        lua, _GOOD % (_TOKEN, "function() error('connection refused') end"))
    assert "missing socket connector" in _start(lua, _GOOD % (_TOKEN, "nil"))
    assert "invalid bridge token" in _start(lua, _GOOD % ("short", ok_conn))
    assert "settings missing or bridge disabled" in _start(lua, "{enabled=false}")
    assert "settings file failed to load: module 'socket' not found" in _start(
        lua, "{enabled=false}", "\"module 'socket' not found\"")
    for result in (_start(lua, _GOOD % (_TOKEN, "nil")), _start(lua, _GOOD % ("short", ok_conn))):
        assert _TOKEN not in result and "s1" not in result


def test_direct_start_surfaces_bridge_reason():
    lua = _runtime()
    result = lua.execute("""
        package.preload.workbench_observation = function() return {is_transition_error=function() return false end} end
        local d = require('workbench_live_direct').new({
            capture = function() return {source_identity='x'} end,
            start_bridge = function() return false, 'receiver unreachable: connection refused' end,
        })
        local ok, err = d.start('ashita-a')
        return tostring(ok) .. '|' .. err
    """)
    assert result == "false|bridge not started: receiver unreachable: connection refused"


def test_generated_settings_defer_socket_require():
    html = (ADDON.parents[1] / "gui/templates/live_client_bridge.html").read_text(encoding="utf-8")
    start = html.index("const lua='-- Private workbench_bridge_settings.lua")
    builder = html[start:html.index(" privateConfig=lua;", start)]
    assert "local socket = require" not in builder
    assert 'pcall(require, "socket")' in builder
