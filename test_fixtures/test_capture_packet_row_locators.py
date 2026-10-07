#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.services import capture_integrity


PACKET_LATE = """[2026-09-28 12:35:00] Packet 0x034
0 | 01 02 03 04 4 |
"""
PACKET_EARLY = """[2026-09-28 12:34:00] Packet 0x032
0 | AA BB CC DD 4 |
"""


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        incoming = root / "PacketLogger" / "incoming"
        incoming.mkdir(parents=True)
        late_path = incoming / "0x034.log"
        early_path = incoming / "0x032.log"
        late_path.write_text(PACKET_LATE, encoding="utf-8")
        early_path.write_text(PACKET_EARLY, encoding="utf-8")

        con = sqlite3.connect(root / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "packet locator test", "Research", None)
        src = build_capture_index.Source(root)
        try:
            relnames = sorted(src.find(r"(?i)PacketLogger/(?:incoming|outgoing)/0x[0-9A-Fa-f]{3}\.log$"))
            assert relnames == [
                "PacketLogger/incoming/0x032.log",
                "PacketLogger/incoming/0x034.log",
            ], relnames
            count = build_capture_index.ingest_packetlogger(con, cid, src, relnames)
        finally:
            src.close()

        assert count == 2, count
        packets = con.execute(
            """SELECT seq,ts,opcode,raw_hex FROM capture_raw_packets
               WHERE capture_id=? ORDER BY seq""",
            (cid,),
        ).fetchall()
        assert packets == [
            (0, "2026-09-28 12:34:00", "0X032", "AABBCCDD"),
            (1, "2026-09-28 12:35:00", "0X034", "01020304"),
        ], packets

        locators = con.execute(
            """SELECT filename,row_key,source_sha256,start_line,end_line,start_offset,end_offset,details_json
               FROM capture_row_locators
               WHERE capture_id=? AND target_table='capture_raw_packets'
               ORDER BY row_key""",
            (cid,),
        ).fetchall()
        assert len(locators) == 2, locators

        by_seq = {json.loads(row[1])["seq"]: row for row in locators}
        early = by_seq[0]
        late = by_seq[1]
        assert early[0] == "PacketLogger/incoming/0x032.log", early
        assert late[0] == "PacketLogger/incoming/0x034.log", late
        assert early[2] == hashlib.sha256(PACKET_EARLY.encode("utf-8")).hexdigest(), early
        assert late[2] == hashlib.sha256(PACKET_LATE.encode("utf-8")).hexdigest(), late

        for seq, row in by_seq.items():
            filename, _, _, start_line, end_line, start_offset, end_offset, details_json = row
            source = (root / filename).read_bytes()
            assert start_line == 1 and end_line == 3, row
            assert start_offset == 0 and end_offset == len(source), row
            assert source[start_offset:end_offset].decode("utf-8").startswith("[2026-09-28"), row
            details = json.loads(details_json)
            assert details["direction"] == "incoming", details
            assert details["opcode"] == packets[seq][2], details
            assert details["timestamp"] == packets[seq][1], details

        health = capture_integrity.capture_health(con, cid)
        assert health["dimensions"]["lineage"]["exact_row_locators"] == 2, health
        assert health["dimensions"]["lineage"]["precision"] == "exact_rows_available", health

        # Re-ingestion is idempotent for both normalized rows and their row locators.
        src = build_capture_index.Source(root)
        try:
            build_capture_index.ingest_packetlogger(con, cid, src, relnames)
        finally:
            src.close()
        assert con.execute(
            "SELECT COUNT(*) FROM capture_row_locators WHERE capture_id=? AND target_table='capture_raw_packets'",
            (cid,),
        ).fetchone()[0] == 2

        con.close()

    print("Capture raw packet row locator regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
