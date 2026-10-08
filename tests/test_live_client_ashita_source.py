"""Ashita v4 SDK observation mapping in Lua 5.1, using synthetic interfaces."""
from pathlib import Path

import pytest

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge

ADDON = Path(__file__).resolve().parents[1] / 'addons' / 'workbench_live'


def runtime(directory):
    module = pytest.importorskip('lupa.lua51')
    lua = module.LuaRuntime(unpack_returned_tuples=True)
    lua.globals().addon_dir = str(ADDON) + '/'
    lua.globals().output_dir = str(directory)
    lua.execute('''
        package.path = addon_dir .. '?.lua;' .. package.path
        package.preload.common = function() return true end
        addon = {path=output_dir}
        clock = 100; os.time = function() return clock end
        events, messages = {}, {}; print = function(text) table.insert(messages, text) end
        party = {active=1, server_id=123, index=1, name='Hero', zone=100}
        function party:GetMemberIsActive(slot) assert(slot==0); return self.active end
        function party:GetMemberServerId(slot) assert(slot==0); return self.server_id end
        function party:GetMemberTargetIndex(slot) assert(slot==0); return self.index end
        function party:GetMemberName(slot) assert(slot==0); return self.name end
        function party:GetMemberZone(slot) assert(slot==0); return self.zone end
        entities = {[1]={name='Hero', zone=100, x=1,y=2,z=3,heading=0.25},
                    [42]={name='Target',zone=100,x=4,y=5,z=6,heading=0.5}}
        entity = {}
        function entity:GetName(index) return entities[index].name end
        function entity:GetZoneId(index) return entities[index].zone end
        function entity:GetLocalPositionX(index) return entities[index].x end
        function entity:GetLocalPositionY(index) return entities[index].y end
        function entity:GetLocalPositionZ(index) return entities[index].z end
        function entity:GetHeading(index) return entities[index].heading end
        target = {index=42}
        function target:GetTargetIndex(slot) assert(slot==0); return self.index end
        memory = {}
        function memory:GetParty() return party end
        function memory:GetEntity() return entity end
        function memory:GetTarget() return target end
        AshitaCore = {}; function AshitaCore:GetMemoryManager() return memory end
        GetEntity = function(index) return entities[index] end
        ashita = {fs={}, events={}}
        ashita.events.register = function(name, _, callback) events[name] = callback end
        ashita.fs.exists = function(path)
            local f=io.open(path,'rb'); if not f then return false end
            f:close();return true
        end
        function command(text)
            local event = {command=text, blocked=false}
            events.command(event)
            return event.blocked
        end
    ''')
    lua.execute((ADDON / 'workbench_live_ashita.lua').read_text())
    return lua


def test_explicit_ashita_export_sdk_fields_and_target_feed_roundtrip(tmp_path):
    lua = runtime(tmp_path)
    assert not list(tmp_path.iterdir())
    assert lua.eval('command("/unrelated-command")') is False
    assert lua.eval('command("/wblive start ashita-a")') is True
    path, = tmp_path.glob('*.jsonl')
    bridge = FileTelemetryBridge(path, 'ashita-a')
    assert bridge.poll() == 1
    frame = bridge.feed._latest
    assert frame.snapshot.adapter == 'ashita-v4-api-experimental'
    assert frame.snapshot.version == 'unverified-ashita-v4-api'
    assert (frame.snapshot.position.x, frame.snapshot.position.y, frame.snapshot.position.z) == (1, 2, 3)
    assert frame.snapshot.position.heading == .25
    assert frame.entities[0].client_index == 42 and frame.entities[0].server_entity_id is None
    assert frame.entities[0].kind.value == 'unknown'
    assert bridge.feed.supports_writes is False and bridge.feed.version_verified is False
    lua.execute('clock=101; entities[1].x=9; events.d3d_present()')
    assert bridge.poll() == 1 and bridge.feed.snapshot().position.x == 9
    lua.execute('command("/wblive stop"); clock=102; events.d3d_present()')
    assert bridge.poll() == 0


@pytest.mark.parametrize('failure', [
    'party.active=0', 'party.server_id=0', 'party.server_id=456', 'party.zone=0',
    'entities[1].name="Different"', 'entities[1].x=0/0', 'clock=99',
    'entity.GetLocalPositionX=nil',
])
def test_ashita_unsupported_or_changed_source_stops_without_consuming_bad_frame(tmp_path, failure):
    lua = runtime(tmp_path)
    lua.execute('command("/wblive start ashita-a")')
    path, = tmp_path.glob('*.jsonl')
    before = path.read_bytes()
    lua.execute('clock=101; ' + failure + '; events.d3d_present(); command("/wblive status")')
    assert path.read_bytes() == before
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]


def test_ashita_missing_target_empty_array_and_unload(tmp_path):
    lua = runtime(tmp_path)
    lua.execute('target.index=0; command("/wblive start ashita-a")')
    path, = tmp_path.glob('*.jsonl')
    bridge = FileTelemetryBridge(path, 'ashita-a')
    assert bridge.poll() == 1 and bridge.feed.entities() == ()
    lua.execute('events.unload(); clock=101; events.d3d_present()')
    assert bridge.poll() == 0


@pytest.mark.parametrize('entity_zone', [0, 101, None])
def test_ashita_entity_zone_is_not_required_for_local_observations(tmp_path, entity_zone):
    lua = runtime(tmp_path)
    lua.globals().entity_zone = entity_zone
    lua.execute('''
        entities[1].zone=entity_zone; entities[42].zone=entity_zone
        -- The field is optional even when the getter itself is unavailable.
        if entity_zone == nil then entity.GetZoneId=nil end
        command('/wblive start ashita-a')
    ''')
    path, = tmp_path.glob('*.jsonl')
    bridge = FileTelemetryBridge(path, 'ashita-a')
    assert bridge.poll() == 1
    assert bridge.feed.snapshot().position.zone_id == 100
    assert bridge.feed.entities()[0].position.zone_id == 100


def test_ashita_zone_transition_during_capture_is_rejected_before_file_creation(tmp_path):
    lua = runtime(tmp_path)
    lua.execute('''
        calls=0
        function party:GetMemberZone(slot) calls=calls+1; return calls==1 and 100 or 101 end
        command('/wblive start ashita-a')
    ''')
    assert not list(tmp_path.iterdir())


def test_ashita_consistent_zone_and_local_slot_change_keep_same_character(tmp_path):
    lua = runtime(tmp_path)
    lua.execute('command("/wblive start ashita-a")')
    path, = tmp_path.glob('*.jsonl')
    bridge = FileTelemetryBridge(path, 'ashita-a')
    assert bridge.poll() == 1
    lua.execute('''
        clock=101; party.zone=101; party.index=2
        entities[2]={name='Hero',zone=101,x=9,y=8,z=7,heading=0.5}
        target.index=0; events.d3d_present()
    ''')
    assert bridge.poll() == 1
    assert bridge.feed.snapshot().position.zone_id == 101
    assert bridge.feed.snapshot().position.x == 9
