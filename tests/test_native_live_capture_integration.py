"""Canonical Capture integration tests for native read-only JSONL sessions."""
import json
import sqlite3

import pytest

from workbench.captures.ingestion import build_index as bci
from workbench.captures.live_capture_jsonl import ingest_session, parse_session


class Source:
    def __init__(self, data):
        self.data = data

    def read_bytes(self, name):
        return self.data


def make_row(seq=1, **updates):
    row = dict(schema_version=1, client_id="ashita-a", session_id="capture-1",
               sequence=seq, observed_at_ns=1760000000000000000 + seq,
               direction="incoming", opcode=0x28, raw_hex="28040000",
               is_injected=False, is_blocked=False, dropped_before=0)
    row.update(updates)
    return (json.dumps(row) + "\n").encode("utf-8")


def capture_db():
    con = sqlite3.connect(":memory:")
    bci.init_db(con)
    cid = bci.create_manual_capture(con, "Native live fixture", "Research", None)
    return con, cid


def test_native_session_to_canonical_capture():
    con, cid = capture_db()
    payload = make_row() + make_row(2, direction="outgoing", dropped_before=2)
    assert ingest_session(con, cid, Source(payload), "native.jsonl") == 2
    rows = con.execute(
        "SELECT direction,opcode,raw_hex,source_format,is_injected,is_blocked "
        "FROM capture_raw_packets ORDER BY seq"
    ).fetchall()
    assert rows == [
        ("incoming", "0x028", "28040000", "native_live_capture", 0, 0),
        ("outgoing", "0x028", "28040000", "native_live_capture", 0, 0),
    ]
    details = [json.loads(x[0]) for x in con.execute(
        "SELECT details_json FROM capture_row_locators ORDER BY start_offset"
    )]
    assert details[0]["client_id"] == "ashita-a"
    assert details[1]["dropped_before"] == 2
    assert details[0]["wire_verified"] is False


def test_invalid_row_never_partially_ingests():
    con, cid = capture_db()
    with pytest.raises(ValueError):
        ingest_session(con, cid, Source(make_row() + make_row(3)), "bad.jsonl")
    assert con.execute("SELECT COUNT(*) FROM capture_raw_packets").fetchone()[0] == 0


def test_sessions_are_distinct_sources():
    con, cid = capture_db()
    assert ingest_session(con, cid, Source(make_row()), "one.jsonl") == 1
    assert ingest_session(con, cid, Source(make_row(session_id="capture-2")), "two.jsonl") == 1
    assert con.execute("SELECT COUNT(*) FROM capture_raw_packets").fetchone()[0] == 2

def test_native_session_auto_discovery_in_capture_upload():
    con, cid = capture_db()
    result = bci.ingest_single_file(con, cid, "native-session.jsonl", make_row())
    assert result["error"] is None
    assert result["format"] == "native_live_capture"
    assert result["rows"] == 1
    saved = con.execute("SELECT source_format,raw_hex FROM capture_raw_packets").fetchone()
    assert saved == ("native_live_capture", "28040000")
