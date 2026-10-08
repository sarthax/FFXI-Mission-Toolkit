"""Execute the experimental addon in Lua 5.1 with synthetic Windower API data.

These tests prove the file-feed contract, never real Windows/client compatibility.
"""
from pathlib import Path

import pytest

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge

ADDON = Path(__file__).resolve().parents[1] / 'addons' / 'workbench_live'


def runtime(directory):
    module = pytest.importorskip('lupa.lua51')
    lua = module.LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + '/'
    lua.globals().output_dir = str(directory) + '/'
    lua.execute('''
        package.path = addon_dir .. '?.lua;' .. package.path
        _addon = {}
        clock = 100
        os.time = function() return clock end
        info = {logged_in=true, zone=100}
        player = {name='Hero', index=1}
        me = {name='Hero', index=1, x=1, y=2, z=3, facing=0.25}
        target = {name='Target', index=42, x=4, y=5, z=6, facing=0.5}
        events, messages = {}, {}
        windower = {addon_path=output_dir, ffxi={}}
        windower.ffxi.get_info = function() return info end
        windower.ffxi.get_player = function() return player end
        windower.ffxi.get_mob_by_target = function(key)
            if key == 'me' then return me end
            if key == 't' or key == 'st' then return target end
        end
        windower.register_event = function(name, callback) events[name] = callback end
        windower.add_to_chat = function(_, message) table.insert(messages, message) end
        windower.file_exists = function(path)
            local f = io.open(path, 'rb')
            if not f then return false end
            f:close(); return true
        end
    ''')
    lua.execute((ADDON / 'workbench_live.lua').read_text())
    return lua


def test_addon_to_strict_file_feed_roundtrip_and_logout(tmp_path):
    lua = runtime(tmp_path)
    assert not list(tmp_path.iterdir()), 'loading the addon must not start exporting'
    lua.execute('events["addon command"]("start", "instance-a")')
    path, = tmp_path.glob('*.jsonl')
    bridge = FileTelemetryBridge(path, 'instance-a')
    assert bridge.poll() == 1
    frame = bridge.feed._latest
    assert frame.snapshot.character == 'Hero'
    assert frame.snapshot.version == 'unverified-windower-api'
    assert frame.snapshot.position.heading == .25
    assert len(frame.entities) == 1  # t/st duplication does not duplicate observations.
    assert frame.entities[0].server_entity_id is None
    assert frame.entities[0].kind.value == 'unknown'
    assert bridge.feed.version_verified is False and bridge.feed.supports_writes is False
    lua.execute('events.prerender()')
    assert bridge.poll() == 0
    lua.execute('clock=101; me.x=9; events.prerender()')
    assert bridge.poll() == 1
    assert bridge.feed.snapshot().position.x == 9
    lua.execute('events.logout(); clock=102; events.prerender()')
    assert bridge.poll() == 0
    lua.execute('events["addon command"]("status")')
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]


@pytest.mark.parametrize('failure', [
    'me.x=math.huge', 'info.logged_in=false', 'player.name="Other"; me.name="Other"',
    'me.index=99', 'clock=99', 'windower.ffxi.get_info=nil',
])
def test_incompatible_or_changed_observations_stop_and_preserve_last_good(tmp_path, failure):
    lua = runtime(tmp_path)
    lua.execute('events["addon command"]("start", "instance-a")')
    path, = tmp_path.glob('*.jsonl')
    before = path.read_bytes()
    lua.execute('clock=101; ' + failure + '; events.prerender()')
    assert path.read_bytes() == before
    lua.execute('events["addon command"]("status")')
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]


def test_existing_exports_preserved_and_text_roundtrips(tmp_path):
    lua = runtime(tmp_path)
    lua.globals().player.name = 'Hero"\\\n'
    lua.globals().me.name = 'Hero"\\\n'
    lua.globals().target.name = 'Unicode café'
    existing = tmp_path / 'telemetry-instance-a-100-1.jsonl'
    existing.write_bytes(b'preserve existing user export\n')
    lua.execute('events["addon command"]("start", "instance-a")')
    assert existing.read_bytes() == b'preserve existing user export\n'
    path = tmp_path / 'telemetry-instance-a-100-2.jsonl'
    bridge = FileTelemetryBridge(path, 'instance-a')
    assert bridge.poll() == 1
    assert bridge.feed.snapshot().character == 'Hero"\\\n'
    assert bridge.feed.entities()[0].name == 'Unicode café'


def test_no_output_without_supported_shape_and_explicit_identity(tmp_path):
    lua = runtime(tmp_path)
    lua.execute('events["addon command"]("start", "../invalid"); info.logged_in=false; events["addon command"]("start", "valid")')
    assert not list(tmp_path.iterdir())
    lua.execute('info.logged_in=true; calls=0; windower.ffxi.get_info=function() calls=calls+1; return {logged_in=true, zone=calls==1 and 100 or 101} end; events["addon command"]("start", "valid")')
    assert not list(tmp_path.iterdir()), 'mixed-zone observations must fail before creating output'


def test_separate_launcher_sources_have_independent_feed_identities(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'; a.mkdir(); b.mkdir()
    first, second = runtime(a), runtime(b)
    first.execute('events["addon command"]("start", "instance-a")')
    second.execute('me.x=20; events["addon command"]("start", "instance-b")')
    feed_a = FileTelemetryBridge(next(a.glob('*.jsonl')), 'instance-a')
    feed_b = FileTelemetryBridge(next(b.glob('*.jsonl')), 'instance-b')
    assert feed_a.poll() == feed_b.poll() == 1
    assert feed_a.feed.snapshot().position.x == 1
    assert feed_b.feed.snapshot().position.x == 20
