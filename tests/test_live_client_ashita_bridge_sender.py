"""Synthetic Ashita LuaSocket bridge frames roundtrip through Python transport."""
import json
import struct
from pathlib import Path

import pytest

from workbench.runtime.live_client.bridge_loopback import decode
from workbench.runtime.live_client.bridge_protocol import BridgeKind, BridgeLane

ADDON = Path(__file__).resolve().parents[1] / "addons" / "workbench_live"


def test_opt_in_ashita_bridge_sends_compatible_authenticated_frames():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True, encoding=None)
    lua.globals().addon_dir = (str(ADDON) + "/").encode("utf-8")
    lua.execute('''
        package.path = addon_dir .. '?.lua;' .. package.path
        output = {}
        fake = {}
        function fake:settimeout(value) return true end
        function fake:send(data) output[#output+1]=data; return #data end
        function fake:close() self.closed=true end
        bridge = require('workbench_bridge').new({
            enabled=true,host='127.0.0.1',port=12345,
            session_id='session',generation='gen',token=string.rep('a',43),
            connect=function(host,port) return fake end
        })
        assert(bridge.start('ashita-a'))
        assert(bridge.observe('ashita-a', '{"schema_version":1,"client_id":"ashita-a"}\\n'))
        bridge.stop()
    ''')
    values = lua.globals().output
    hello, wire = (values[1], values[2])
    assert json.loads(hello[2:])["client_id"] == "ashita-a"
    assert struct.unpack("!H", hello[:2])[0] == len(hello) - 2
    assert struct.unpack("!I", wire[:4])[0] == len(wire) - 4
    frame = decode(wire[4:])
    assert frame.lane is BridgeLane.TELEMETRY and frame.kind is BridgeKind.OBSERVATION
    assert frame.client_id == "ashita-a" and frame.session_id == "session"
    assert json.loads(frame.payload)["client_id"] == "ashita-a"


def test_bridge_sender_fails_closed_on_other_client_or_invalid_network_config():
    lua = pytest.importorskip("lupa.lua51").LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + "/"
    lua.execute('''
        package.path = addon_dir .. '?.lua;' .. package.path
        called=false
        bridge = require('workbench_bridge').new({
            enabled=true,host='0.0.0.0',port=12345,session_id='s',
            generation='g',token=string.rep('a',43),
            connect=function() called=true end
        })
        assert(not bridge.start('one'))
        assert(not called)
        bridge = require('workbench_bridge').new({
            enabled=true,host='127.0.0.1',port=12345,session_id='s',
            generation='g',token=string.rep('a',43),
            connect=function() return {
                settimeout=function() return true end,
                send=function(_, data) return #data end,
                close=function() end
            } end
        })
        assert(bridge.start('one'))
        assert(not bridge.observe('other','{}'))
        assert(not bridge.active())
    ''')
