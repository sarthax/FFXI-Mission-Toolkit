"""Passive original-byte hooks reuse canonical Capture with synthetic Ashita APIs."""
import json
import sqlite3

import pytest

from test_live_client_ashita_source import runtime
from workbench.captures.ashita_packet_ingest import parse_observations, ingest_ashita_packets
from workbench.captures.ingestion import build_index as bci
from workbench.packets import decode as packet_decode


def event(lua, **changes):
    lua.execute('packet={id=0x034,size=32,data=string.char(0x34,0x10,0,0)..string.rep("A",28),data_modified="modified",injected=false,blocked=false}')
    for key, value in changes.items():
        lua.globals().packet[key] = value
    return lua.globals().packet


def start(lua):
    lua.execute('command("/wblive start packet-a"); command("/wblive packets start event_emote")')


def test_explicit_passive_original_bytes_and_canonical_capture_upload(tmp_path):
    lua = runtime(tmp_path)
    e = event(lua)
    lua.globals().events.packet_in(e)
    assert not list(tmp_path.glob('packets-*'))
    lua.execute('command("/wblive packets start event_emote")')
    assert not list(tmp_path.glob('packets-*'))
    start(lua); path, = tmp_path.glob('packets-*')
    lua.globals().events.packet_in(e)
    assert e.data_modified == 'modified' and e.blocked is False and e.injected is False
    row, = [json.loads(line) for line in path.read_text().splitlines()]
    assert row['raw_hex'] == e.data.encode().hex().upper()
    assert row['zone_id'] == 100 and row['direction'] == 'incoming'
    con = sqlite3.connect(':memory:'); bci.init_db(con)
    cid = bci.create_manual_capture(con, 'Ashita fixture', 'Research', None)
    result = bci.ingest_single_file(con, cid, path.name, path.read_bytes())
    assert result['error'] is None and result['rows'] == 1 and result['format'] == 'ashita_packets'
    saved = con.execute('SELECT direction,raw_hex,opcode,is_injected,is_blocked FROM capture_raw_packets').fetchone()
    assert saved == ('incoming', row['raw_hex'], '0x034', 0, 0)
    locator = con.execute("SELECT details_json FROM capture_row_locators WHERE target_table='capture_raw_packets'").fetchone()
    details = json.loads(locator[0])
    assert details['client_id'] == 'packet-a' and details['source_recording'] == row['source_recording']
    assert details['wire_verified'] is False and details['opcode_semantics_verified'] is False
    result = bci.ingest_single_file(con, cid, path.name, path.read_bytes())
    assert result['error'] is None and con.execute('SELECT COUNT(*) FROM capture_raw_packets').fetchone()[0] == 1
    con.close()


def test_profile_filter_rate_bounds_directions_flags_and_shutdown(tmp_path):
    lua = runtime(tmp_path); start(lua)
    path, = tmp_path.glob('packets-*')
    e = event(lua, id=0x017); lua.globals().events.packet_in(e)  # Excluded chat opcode.
    assert path.read_bytes() == b''
    e = event(lua)
    for _ in range(12): lua.globals().events.packet_in(e)
    assert len(path.read_text().splitlines()) == 10
    lua.execute('clock=101')
    e = event(lua, id=0x05D, injected=True, blocked=True)
    lua.globals().events.packet_out(e)
    rows = parse_observations(path.read_bytes())
    assert rows[-1][0]['direction'] == 'outgoing'
    assert rows[-1][0]['is_injected'] is True and rows[-1][0]['is_blocked'] is True
    assert rows[-1][0]['dropped_before'] == 2
    assert e.blocked is True and e.data_modified == 'modified'
    before = path.read_bytes()
    lua.execute('events.unload()'); lua.globals().events.packet_out(e)
    assert path.read_bytes() == before


@pytest.mark.parametrize('failure', ['party.active=0', 'party.server_id=456', 'party.zone=0', 'clock=99',
                                     'packet.size=31', 'packet.size=1025', 'packet.injected=nil', 'packet.data=nil'])
def test_invalid_packet_or_disconnected_source_stops_without_bad_append(tmp_path, failure):
    lua = runtime(tmp_path); start(lua); event(lua)
    lua.execute('events.packet_in(packet)')
    path, = tmp_path.glob('packets-*'); before = path.read_bytes()
    lua.execute(failure+'; events.packet_in(packet); command("/wblive packets status")')
    assert path.read_bytes() == before
    assert 'Packets inactive' in lua.globals().messages[len(lua.globals().messages)]


def test_telemetry_stop_restart_binds_new_packet_file(tmp_path):
    lua = runtime(tmp_path); start(lua); e = event(lua)
    lua.globals().events.packet_in(e)
    old, = tmp_path.glob('packets-*'); before = old.read_bytes()
    lua.execute('command("/wblive stop"); command("/wblive start packet-a"); command("/wblive packets start event_emote")')
    lua.globals().events.packet_in(e)
    assert len(list(tmp_path.glob('packets-*'))) == 2
    assert old.read_bytes() == before


def test_file_bound_fails_closed(tmp_path):
    lua = runtime(tmp_path); start(lua)
    lua.execute('packet={id=0x034,size=1024,data=string.rep("A",1024),injected=false,blocked=false}; for i=1,2100 do clock=100+i; events.packet_in(packet) end; command("/wblive packets status")')
    path, = tmp_path.glob('packets-*')
    assert 0 < path.stat().st_size <= 4*1024*1024
    assert len(parse_observations(path.read_bytes())) < 2100
    assert 'Packets inactive' in lua.globals().messages[len(lua.globals().messages)]


def test_folder_ingest_unknown_opcode_provenance_and_invalid_tail_are_isolated(tmp_path):
    lua = runtime(tmp_path); start(lua); lua.globals().events.packet_in(event(lua))
    path, = tmp_path.glob('packets-*'); row = json.loads(path.read_text())
    row['opcode'] = 511  # Preserve an unknown hook-reported opcode without assigning meaning.
    path.write_text(json.dumps(row)+'\n')
    con = sqlite3.connect(':memory:'); bci.init_db(con)
    cid = bci.create_manual_capture(con, 'source folder', 'Research', None)
    folder = tmp_path / 'capture-source'; folder.mkdir()
    (folder / path.name).write_bytes(path.read_bytes())
    src = bci.Source(folder)
    try:
        results = []
        bci.ingest_from_source(con, cid, src, file_results=results)
        assert not [result for result in results if result['error']]
    finally:
        src.close()
    saved = con.execute('SELECT opcode,raw_hex FROM capture_raw_packets').fetchone()
    assert saved == ('0x1FF', row['raw_hex'])
    decoded = packet_decode.decode('incoming', 511, row['raw_hex'])
    assert not decoded.fields  # Existing decoder, no invented semantic fallback.
    con.execute('UPDATE captures SET source_path=? WHERE capture_id=?', (str(folder), cid))
    rebuilt = bci.rebuild_capture_source(con, cid, path.name)
    assert rebuilt['rows'] == 1
    assert con.execute('SELECT COUNT(*) FROM capture_raw_packets').fetchone()[0] == 1
    src = bci.SingleFileSource('bad.jsonl', path.read_bytes()+b'{"broken":true}\n')
    with pytest.raises(ValueError): ingest_ashita_packets(con, cid, src, 'bad.jsonl')
    assert con.execute('SELECT COUNT(*) FROM capture_raw_packets').fetchone()[0] == 1
    for failure in (path.read_bytes().rstrip(b'\n'), b'x'*4097+b'\n'):
        with pytest.raises(ValueError): parse_observations(failure)
    con.close()


def test_same_client_source_files_remain_independent(tmp_path):
    lua = runtime(tmp_path); start(lua); lua.globals().events.packet_in(event(lua))
    path, = tmp_path.glob('packets-*')
    con = sqlite3.connect(':memory:'); bci.init_db(con)
    cid = bci.create_manual_capture(con, 'two sources', 'Research', None)
    for name in ('client-a/packets.jsonl', 'client-b/packets.jsonl'):
        result = bci.ingest_single_file(con, cid, name, path.read_bytes())
        assert result['rows'] == 1 and result['error'] is None
    assert con.execute('SELECT COUNT(DISTINCT source_native_id) FROM capture_raw_packets').fetchone()[0] == 2
    con.close()


def test_packet_zone_transition_and_mid_sample_change(tmp_path):
    lua = runtime(tmp_path); start(lua); e = event(lua)
    lua.globals().events.packet_in(e)
    lua.execute('clock=101; party.zone=101; events.packet_in(packet)')
    path, = tmp_path.glob('packets-*')
    assert [row[0]['zone_id'] for row in parse_observations(path.read_bytes())] == [100, 101]
    before = path.read_bytes()
    lua.execute('clock=102; calls=0; function party:GetMemberZone(slot) calls=calls+1; return calls==1 and 101 or 102 end; events.packet_in(packet)')
    assert path.read_bytes() == before


def test_database_error_rolls_back_all_new_packet_rows(tmp_path, monkeypatch):
    from workbench.captures import ashita_packet_ingest
    lua = runtime(tmp_path); start(lua); e = event(lua)
    lua.globals().events.packet_in(e); lua.globals().events.packet_in(e)
    path, = tmp_path.glob('packets-*')
    con = sqlite3.connect(':memory:'); bci.init_db(con)
    cid = bci.create_manual_capture(con, 'atomic', 'Research', None)
    original = ashita_packet_ingest.raw_packet_ingest.insert_raw_packet
    calls = 0
    def failing(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise sqlite3.OperationalError('simulated storage failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(ashita_packet_ingest.raw_packet_ingest, 'insert_raw_packet', failing)
    src = bci.SingleFileSource(path.name, path.read_bytes())
    with pytest.raises(sqlite3.OperationalError):
        ingest_ashita_packets(con, cid, src, path.name)
    assert con.execute('SELECT COUNT(*) FROM capture_raw_packets').fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM capture_row_locators WHERE target_table='capture_raw_packets'").fetchone()[0] == 0
    con.close()


@pytest.mark.parametrize('field,value', [('direction','wire'), ('size',33), ('raw_hex','xyz'),
    ('sequence',2), ('observed_at',True), ('is_blocked',1), ('kind','telemetry'),
    ('hook_stage','modified'), ('client_id',''), ('opcode',512)])
def test_invalid_import_is_atomic(tmp_path, field, value):
    lua = runtime(tmp_path); start(lua); lua.globals().events.packet_in(event(lua))
    path, = tmp_path.glob('packets-*')
    row = json.loads(path.read_text()); row[field] = value
    con = sqlite3.connect(':memory:'); bci.init_db(con)
    cid = bci.create_manual_capture(con, 'invalid', 'Research', None)
    src = bci.SingleFileSource('bad.jsonl', (json.dumps(row)+'\n').encode())
    with pytest.raises(ValueError): ingest_ashita_packets(con, cid, src, 'bad.jsonl')
    assert con.execute('SELECT COUNT(*) FROM capture_raw_packets').fetchone()[0] == 0
    con.close()
