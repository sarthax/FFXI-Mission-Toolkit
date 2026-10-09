"""Canonical Capture handoffs remain bounded, read-only and context-specific."""
import json
import sqlite3

import pytest

from test_live_client_runtime_report import CAPTURE, packet_file
from workbench.captures.ingestion import build_index as bci
from workbench.runtime.live_client.runtime_report import main, recording_report


def imported(tmp_path, *, duplicate=False):
    packet = packet_file(tmp_path)
    database = tmp_path / 'capture database.sqlite'
    with sqlite3.connect(database) as con:
        bci.init_db(con)
        cid = bci.create_manual_capture(con, 'Synthetic Live Client packets', 'Research', None)
        result = bci.ingest_single_file(con, cid, 'logs/packets.jsonl', packet.read_bytes())
        assert result['error'] is None
        if duplicate:
            assert bci.ingest_single_file(con, cid, 'other/packets.jsonl', packet.read_bytes())['error'] is None
    return packet, database, cid


def evidence(packet, database, cid):
    return recording_report(CAPTURE, packet_observations=packet,
                            capture_database=database, capture_id=cid)['packet_evidence']


def test_exact_packet_locators_reuse_existing_view_and_leave_database_unchanged(tmp_path):
    packet, database, cid = imported(tmp_path)
    original = database.read_bytes()
    report = evidence(packet, database, cid)
    assert database.read_bytes() == original
    candidate, = report['candidates']
    assert candidate['capture_lookup'] == 'exact_imported_packet'
    locator = candidate['capture_locator']
    assert locator['href'] == f'/captures/{cid}/packets/0'
    assert locator['source_filename'] == 'logs/packets.jsonl'
    assert locator['runtime_identity_verified'] is False
    assert report['capture_lookup']['classification_counts'] == {'exact_imported_packet': 1}
    assert report['capture_lookup']['read_only'] is True
    assert report['packet_semantics_verified'] is False  # Unknown hook opcode remains uninterpreted.


def test_same_source_under_multiple_names_remains_ambiguous(tmp_path):
    packet, database, cid = imported(tmp_path, duplicate=True)
    report = evidence(packet, database, cid)
    assert report['candidates'][0]['capture_lookup'] == 'ambiguous_locator'
    assert 'capture_locator' not in report['candidates'][0]


@pytest.mark.parametrize('sql', [
    "UPDATE capture_raw_packets SET raw_hex='01020304'",
    "UPDATE capture_raw_packets SET source_format='packetdb'",
    "UPDATE capture_raw_packets SET zone_id=51",
    "UPDATE capture_raw_packets SET ts='different-time'",
    "UPDATE capture_raw_packets SET opcode='0x034'",
    "UPDATE capture_raw_packets SET is_blocked=1",
    "UPDATE capture_raw_packets SET source_native_id='different-source'",
    "UPDATE capture_row_locators SET details_json='{}'",
    "UPDATE capture_row_locators SET row_key='[]'",
    "UPDATE capture_row_locators SET row_key='null'",
    "UPDATE capture_row_locators SET row_key='{\"seq\": true}'",
    "UPDATE capture_row_locators SET details_json='invalid'",
])
def test_changed_or_invalid_stored_evidence_never_receives_a_link(tmp_path, sql):
    packet, database, cid = imported(tmp_path)
    with sqlite3.connect(database) as con:
        con.execute(sql)
    report = evidence(packet, database, cid)
    assert report['candidates'][0]['capture_lookup'] == 'stored_evidence_mismatch'
    assert 'capture_locator' not in report['candidates'][0]


@pytest.mark.parametrize('sql', [
    "UPDATE capture_row_locators SET source_sha256='different-hash'",
    "UPDATE capture_row_locators SET start_offset=1",
    "UPDATE capture_row_locators SET end_line=2",
])
def test_hash_and_source_span_are_required(tmp_path, sql):
    packet, database, cid = imported(tmp_path)
    with sqlite3.connect(database) as con:
        con.execute(sql)
    candidate, = evidence(packet, database, cid)['candidates']
    assert candidate['capture_lookup'] == 'not_imported'
    assert 'capture_locator' not in candidate


def test_capture_selection_is_explicit_and_isolated(tmp_path):
    packet, database, cid = imported(tmp_path)
    with sqlite3.connect(database) as con:
        other = bci.create_manual_capture(con, 'Other client', 'Research', None)
    assert evidence(packet, database, other)['candidates'][0]['capture_lookup'] == 'not_imported'
    with pytest.raises(ValueError, match='does not exist'):
        evidence(packet, database, cid+100)
    for invalid in (0, -1, True, 2**63):
        with pytest.raises(ValueError, match='positive SQLite integer'):
            evidence(packet, database, invalid)


def test_missing_database_is_not_created_and_schema_failure_is_controlled(tmp_path):
    packet = packet_file(tmp_path)
    database = tmp_path / 'missing.sqlite'
    with pytest.raises(ValueError, match='Capture lookup failed'):
        evidence(packet, database, 1)
    assert not database.exists()
    sqlite3.connect(database).close()
    with pytest.raises(ValueError, match='Capture lookup failed'):
        evidence(packet, database, 1)


def test_cli_complete_arguments_and_exclusive_output(tmp_path):
    packet, database, cid = imported(tmp_path)
    output = tmp_path / 'report.json'
    args = [str(CAPTURE), '--packet-observations', str(packet), '--capture-database', str(database),
            '--capture-id', str(cid), '--output', str(output)]
    assert main(args) == 0
    original = output.read_bytes()
    assert json.loads(original)['packet_evidence']['candidates'][0]['capture_locator']['capture_id'] == cid
    with pytest.raises(SystemExit):
        main(args)
    assert output.read_bytes() == original
    for partial in ([str(CAPTURE), '--capture-id', str(cid)],
                    [str(CAPTURE), '--capture-database', str(database)],
                    [str(CAPTURE), '--capture-database', str(database), '--capture-id', str(cid)]):
        with pytest.raises(SystemExit):
            main(partial)


def test_capture_binding_uses_the_same_immutable_packet_snapshot(tmp_path, monkeypatch):
    from workbench.runtime.live_client import runtime_report
    packet, database, cid = imported(tmp_path)
    original = packet.read_bytes()
    read = runtime_report.bounded_bytes
    def changing_source(path, limit):
        data = read(path, limit)
        if path == packet:
            packet.write_bytes(b'changed after read\n')
        return data
    monkeypatch.setattr(runtime_report, 'bounded_bytes', changing_source)
    report = evidence(packet, database, cid)
    import hashlib
    assert report['sha256'] == hashlib.sha256(original).hexdigest()
    assert report['candidates'][0]['capture_lookup'] == 'exact_imported_packet'
