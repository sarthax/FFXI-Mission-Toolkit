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
    assert "require('workbench_bridge').new(bridge_options)" in entry
