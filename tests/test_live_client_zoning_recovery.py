"""Opt-in transition recovery uses synthetic Ashita APIs; Windows testing pending."""
import json

import pytest

from test_live_client_ashita_source import runtime
from workbench.runtime.live_client.runtime_report import recording_report


def start(tmp_path):
    lua = runtime(tmp_path)
    lua.execute('command("/wblive start zoning inventory-zoning")')
    path, = tmp_path.glob('telemetry-*.jsonl')
    return lua, path


def pause(lua):
    lua.execute('clock=101; entities[1].name="Transient"; events.d3d_present(); command("/wblive status")')
    assert 'Paused' in lua.globals().messages[len(lua.globals().messages)]


def test_opt_in_pause_resumes_same_identity_after_two_coherent_zone_samples(tmp_path):
    lua, path = start(tmp_path); original = path.read_bytes()
    pause(lua)
    lua.execute('events.d3d_present(); clock=102; events.d3d_present()')
    assert path.read_bytes() == original
    lua.execute('clock=103; party.zone=101; entities[1].name="Hero"; events.d3d_present()')
    assert path.read_bytes() == original
    lua.execute('clock=104; events.d3d_present(); command("/wblive status")')
    assert 'Exporting' in lua.globals().messages[len(lua.globals().messages)]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r['position']['zone_id'] for r in rows] == [100, 101]
    assert [r['observed_at'] for r in rows] == [100, 104]
    report = recording_report(path)['recording']
    assert report['context_transitions'][0]['to_zone'] == 101
    assert report['frame_intervals'] == [{'seconds': 4, 'count': 1}]


@pytest.mark.parametrize('failure', [
    'party.active=0',
    'party.server_id=456; entities[1].name="Hero"',
    'party.name="Other"; entities[1].name="Other"',
    'entities[1].name="Hero"; entities[1].x=0/0',
    'clock=99',
    'clock=131',
])
def test_pause_stops_on_logout_changed_identity_invalid_data_clock_or_timeout(tmp_path, failure):
    lua, path = start(tmp_path); pause(lua); original = path.read_bytes()
    lua.execute('clock=102; '+failure+'; events.d3d_present(); command("/wblive status")')
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]
    assert path.read_bytes() == original


def test_stability_resets_for_zone_change_and_failed_sample(tmp_path):
    lua, path = start(tmp_path); pause(lua)
    lua.execute('clock=102; entities[1].name="Hero"; events.d3d_present(); clock=103; party.zone=101; events.d3d_present()')
    assert len(path.read_text().splitlines()) == 1
    lua.execute('clock=104; entities[1].name="Transient"; events.d3d_present(); clock=105; entities[1].name="Hero"; events.d3d_present()')
    assert len(path.read_text().splitlines()) == 1
    lua.execute('clock=106; events.d3d_present()')
    assert len(path.read_text().splitlines()) == 2


def test_pause_stops_packet_stream_and_does_not_automatically_restart_it(tmp_path):
    lua, path = start(tmp_path)
    lua.execute('command("/wblive packets start event_emote")')
    packet, = tmp_path.glob('packets-*')
    pause(lua)
    lua.execute('command("/wblive packets status")')
    assert 'telemetry inactive or paused' in lua.globals().messages[len(lua.globals().messages)]
    message_count = len(lua.globals().messages)
    lua.execute('events.d3d_present(); events.d3d_present()')
    assert len(lua.globals().messages) == message_count
    lua.execute('clock=102; entities[1].name="Hero"; events.d3d_present(); clock=103; events.d3d_present(); events.packet_in({id=0x034,size=4,data="ABCD",injected=false,blocked=false})')
    assert len(path.read_text().splitlines()) == 2
    assert packet.read_bytes() == b''


def test_timeout_cannot_be_extended_by_intermittent_valid_frames(tmp_path):
    lua, path = start(tmp_path); pause(lua)
    lua.execute('clock=129; entities[1].name="Hero"; events.d3d_present(); clock=131; events.d3d_present(); command("/wblive status")')
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]
    assert len(path.read_text().splitlines()) == 1


def test_explicit_stop_unload_and_restart_preserve_paused_file(tmp_path):
    lua, path = start(tmp_path); pause(lua); original = path.read_bytes()
    lua.execute('command("/wblive stop"); entities[1].name="Hero"; clock=102; command("/wblive start next inventory-zoning"); events.unload(); clock=103; events.d3d_present(); command("/wblive status")')
    assert path.read_bytes() == original
    assert len(list(tmp_path.glob('telemetry-*'))) == 2
    assert 'Not exporting' in lua.globals().messages[len(lua.globals().messages)]

def test_packet_restart_after_zoning_needs_new_telemetry_file(tmp_path):
    lua, telemetry = start(tmp_path)
    lua.execute('command("/wblive packets start event_emote")')
    packet, = tmp_path.glob('packets-*')
    lua.execute('events.packet_in({id=0x034,size=4,data="ABCD",injected=false,blocked=false})')
    before = packet.read_bytes()
    pause(lua)
    lua.execute('clock=102; party.zone=101; entities[1].name="Hero"; events.d3d_present(); clock=103; events.d3d_present()')
    assert len(telemetry.read_text().splitlines()) == 2
    lua.execute('command("/wblive packets start event_emote")')
    assert packet.read_bytes() == before
    assert len(list(tmp_path.glob('packets-*'))) == 1
    lua.execute('command("/wblive stop"); clock=104; command("/wblive start after-zone inventory-zoning"); command("/wblive packets start event_emote")')
    packet_files = list(tmp_path.glob('packets-*'))
    assert len(packet_files) == 2
    assert packet.read_bytes() == before
    lua.execute('events.packet_in({id=0x034,size=4,data="EFGH",injected=false,blocked=false})')
    new_packet, = [p for p in packet_files if p != packet]
    assert len(new_packet.read_text().splitlines()) == 1
    assert packet.read_bytes() == before

