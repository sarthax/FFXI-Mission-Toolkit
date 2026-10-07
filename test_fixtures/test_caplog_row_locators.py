#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index


CAPLOG = """[12:00:00] === Area: Test Zone ===
[12:00:01] [ID View] INCOMING < CS Event + Params (0x034): NPC: 17000001 (Test NPC), Event: 409, Params: {1,2}, Option: 0, Message: 123
[12:00:02] [HP Track] Killed 17000002 (Test Mob): 100~120HP
[12:00:03] [EView] << [0x034] CEventPacket (GP_SERV_COMMAND_EVENT)
UniqueNo: 17000001 (Test NPC), EventNum: 409
[12:00:04] Obtained temporary item.
"""


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        cap_dir = root / "caplog"
        cap_dir.mkdir()
        relname = "caplog/test.txt"
        payload = CAPLOG.encode("utf-8")
        (root / relname).write_bytes(payload)

        con = sqlite3.connect(root / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "caplog locators", "Research", None)

        src = build_capture_index.Source(root)
        try:
            counts = build_capture_index.ingest_caplog(con, cid, src, relname)
        finally:
            src.close()
        assert counts == (1, 1, 1, 1), counts

        rows = con.execute(
            """SELECT target_table,row_key,source_sha256,locator_basis,
                      start_line,end_line,start_offset,end_offset,details_json
               FROM capture_row_locators
               WHERE capture_id=? AND filename=?
               ORDER BY start_line""",
            (cid, relname),
        ).fetchall()
        assert len(rows) == 5, rows
        digest = hashlib.sha256(payload).hexdigest()
        assert all(r[2] == digest for r in rows), rows

        by_table = {r[0]: r for r in rows}
        assert by_table["capture_events"][4:6] == (2, 2), by_table["capture_events"]
        assert by_table["capture_hp_events"][4:6] == (3, 3), by_table["capture_hp_events"]
        assert by_table["capture_eventview"][4:6] == (4, 5), by_table["capture_eventview"]
        assert by_table["capture_caplog_chat"][4:6] == (6, 6), by_table["capture_caplog_chat"]
        assert by_table["capture_chat_observations"][4:6] == (6, 6), by_table["capture_chat_observations"]

        for row in rows:
            target, row_key, _digest, basis, start_line, end_line, start_offset, end_offset, details = row
            assert basis in {"line", "block"}, row
            source_slice = payload[start_offset:end_offset].decode("utf-8")
            assert source_slice, row
            if target == "capture_eventview":
                assert source_slice.startswith("[12:00:03] [EView]")
                assert "UniqueNo: 17000001" in source_slice
                key = json.loads(row_key)
                assert key["zone_db"] == "Test Zone"
                assert key["seq"] == build_capture_index.CAPLOG_SEQ_BASE
            elif target == "capture_events":
                assert source_slice.startswith("[12:00:01] [ID View]")
            elif target == "capture_hp_events":
                assert source_slice.startswith("[12:00:02] [HP Track]")
            elif target in {"capture_caplog_chat", "capture_chat_observations"}:
                assert source_slice.startswith("[12:00:04] Obtained temporary item.")
            assert json.loads(details)["source"] == "caplog"

        event = con.execute(
            """SELECT entity_id,event_hex,option,message_id
               FROM capture_events WHERE capture_id=? AND zone_db='Test Zone'""",
            (cid,),
        ).fetchone()
        assert event == (17000001, "0x0199", 0, 123), event

        eview = con.execute(
            """SELECT entity_id,opcode,packet_class,gp_command
               FROM capture_eventview WHERE capture_id=? AND zone_db='Test Zone'""",
            (cid,),
        ).fetchone()
        assert eview == (17000001, "0x034", "CEventPacket", "GP_SERV_COMMAND_EVENT"), eview

        canonical_chat = con.execute(
            """SELECT ts,direction,zone_id,zone_db,text,source_format
               FROM capture_chat_observations WHERE capture_id=?""",
            (cid,),
        ).fetchone()
        assert canonical_chat == (
            "12:00:04", None, None, "Test Zone", "Obtained temporary item.", "caplog"
        ), canonical_chat

        src = build_capture_index.Source(root)
        try:
            build_capture_index.ingest_caplog(con, cid, src, relname)
        finally:
            src.close()
        assert con.execute(
            "SELECT COUNT(*) FROM capture_row_locators WHERE capture_id=? AND filename=?",
            (cid, relname),
        ).fetchone()[0] == 5

        con.close()

    print("CapLog exact row locator regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
