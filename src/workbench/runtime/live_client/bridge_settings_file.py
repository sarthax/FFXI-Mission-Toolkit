"""Render and write the private Ashita workbench_bridge_settings.lua.

Never logs credentials. The write targets only the validated workbench_live addon folder.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .ashita_install import _paths

SETTINGS_NAME = "workbench_bridge_settings.lua"


def render_settings_lua(creds: dict) -> str:
    """Lua text with real line breaks; LuaSocket is required lazily inside connect()."""
    return (
        "-- Private workbench_bridge_settings.lua; do not commit this file.\n"
        "return {\n"
        '  enabled = true, host = "127.0.0.1",\n'
        f"  port = {int(creds['port'])},\n"
        f"  session_id = {json.dumps(creds['session_id'])},\n"
        f"  generation = {json.dumps(creds['generation'])},\n"
        f"  token = {json.dumps(creds['token'])},\n"
        "  connect = function(host, port)\n"
        '    local loaded, socket = pcall(require, "socket")\n'
        '    if not loaded or type(socket) ~= "table" or type(socket.tcp) ~= "function" then error("LuaSocket unavailable in this Ashita runtime") end\n'
        "    local peer = assert(socket.tcp())\n"
        "    peer:settimeout(0.1)\n"
        "    local ok, err = peer:connect(host, port)\n"
        "    if not ok then peer:close(); error(err) end\n"
        "    return peer\n"
        "  end,\n"
        "}\n"
    )


def write_settings(ashita_root: str, creds: dict) -> tuple[Path, bool]:
    """Write settings into <root>/addons/workbench_live; returns (path, changed)."""
    addon = _paths(ashita_root)
    addon.mkdir(exist_ok=True)
    target = addon / SETTINGS_NAME
    text = render_settings_lua(creds)
    if target.is_symlink():
        raise ValueError("Refusing to write through a symlinked settings file")
    if target.exists() and target.read_text(encoding="utf-8") == text:
        return target, False
    temp = target.with_suffix(".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, target)
    return target, True
