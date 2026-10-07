#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as bci
from workbench.core.services import capture_integrity
from workbench.core.services import packet_correlation


RAW_BYTES = "0E 08 34 12 AA BB CC DD 00 00 00 00 00 00 00 00"
RAW_COMPACT = RAW_BYTES.replace(" ", "")

PACKETVIEWER = f"""[2026-09-28 12:00:00] Packet 0x00E
0 | {RAW_BYTES} 16 |
"""

PACKETEER = f"""[S->C] PacketId: 000E | HeaderSize: 28
    {RAW_BYTES}

"""

NPCLOGGER = (
    "[17000001] = {['id']=17000001, ['name']=\"Test_NPC\", ['index']=1, "
    "['x']=1.0, ['y']=2.0, ['z']=3.0, ['r']=4, ['flags']=0, ['status']=0, "
    "['animation']=0, ['speed']=0, ['raw_packet']=\"" + RAW_COMPACT + "\"},\n"
)


def make_packetdb(path: Path):
    con = sqlite3.connect(path)
    con.execute(
        """CREATE TABLE PACKETS (
            PACKET_ID INTEGER PRIMARY KEY,
            RECEIVED_DT DATETIME NOT NULL,
            DIRECTION INTEGER NOT NULL,
            ZONE_ID INTEGER,
            PACKET_TYPE INTEGER NOT NULL,
            PACKET_SIZE INTEGER NOT NULL,
            PACKET_SYNC INTEGER NOT NULL,
            PACKET_DATA TEXT NOT NULL
        )"""
    )
    con.execute(
        """INSERT INTO PACKETS
           (PACKET_ID,RECEIVED_DT,DIRECTION,ZONE_ID,PACKET_TYPE,PACKET_SIZE,PACKET_SYNC,PACKET_DATA)
           VALUES (?,?,?,?,?,?,?,?)""",
        (1, "2026-09-28 12:00:00", 0, 75, 0x00E, 16, 0x1234, RAW_BYTES),
    )
    con.execute(
        """CREATE TABLE CHATLOG (
            CHAT_ID INTEGER PRIMARY KEY,
            RECEIVED_DT DATETIME NOT NULL,
            DIRECTION INTEGER NOT NULL,
            ZONE_ID INTEGER,
            CHAT_TEXT TEXT NOT NULL
        )"""
    )
    con.execute(
        """INSERT INTO CHATLOG (CHAT_ID,RECEIVED_DT,DIRECTION,ZONE_ID,CHAT_TEXT)
           VALUES (?,?,?,?,?)""",
        (7, "2026-09-28 12:00:01", 0, 75, "PacketDB chat sample"),
    )
    con.commit()
    con.close()


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_root = root / "source"
        source_root.mkdir()
        (source_root / "PacketViewer" / "incoming").mkdir(parents=True)
        (source_root / "PacketViewer" / "incoming" / "0x00E.log").write_text(
            PACKETVIEWER, encoding="utf-8"
        )
        (source_root / "packeteer.txt").write_text(PACKETEER, encoding="utf-8")
        make_packetdb(source_root / "packetdb.sqlite")
        (source_root / "npclogger" / "tables").mkdir(parents=True)
        (source_root / "npclogger" / "tables" / "Test Zone.lua").write_text(
            NPCLOGGER, encoding="utf-8"
        )

        db = root / "capture.db"
        con = sqlite3.connect(db)
        bci.init_db(con)
        cid = bci.create_manual_capture(con, "packet adapter fixture", "Research", None)

        src = bci.Source(source_root)
        results = []
        try:
            bci.ingest_from_source(con, cid, src, file_results=results)
        finally:
            src.close()

        failures = [row for row in results if row["error"]]
        assert failures == [], failures

        rows = con.execute(
            """SELECT direction,opcode,raw_hex,zone_id,packet_size,sync_id,
                      source_format,source_native_id
               FROM capture_raw_packets WHERE capture_id=? ORDER BY source_format""",
            (cid,),
        ).fetchall()
        assert len(rows) == 4, rows
        assert {row[6] for row in rows} == {
            "packetviewer", "packetdb", "packeteer", "npclogger_lua"
        }, rows
        assert {row[2] for row in rows} == {RAW_COMPACT}, rows
        assert {row[4] for row in rows} == {16}, rows
        assert {row[5] for row in rows} == {0x1234}, rows

        packetdb = next(row for row in rows if row[6] == "packetdb")
        assert packetdb[0] == "incoming", packetdb
        assert packetdb[3] == 75, packetdb

        chat_rows = con.execute(
            """SELECT ts,direction,zone_id,zone_db,text,source_format,source_native_id
               FROM capture_chat_observations WHERE capture_id=? ORDER BY seq""",
            (cid,),
        ).fetchall()
        packetdb_chat = next(row for row in chat_rows if row[5] == "packetdb_chatlog")
        assert packetdb_chat[:5] == (
            "2026-09-28 12:00:01", "incoming", 75, None, "PacketDB chat sample"
        ), packetdb_chat
        assert packetdb_chat[6].endswith(":chat:7"), packetdb_chat

        packeteer = next(row for row in rows if row[6] == "packeteer")
        assert packeteer[0] == "incoming", packeteer
        assert packeteer[1].lower() == "0x00e", packeteer

        npcl = next(row for row in rows if row[6] == "npclogger_lua")
        assert npcl[0] == "incoming", npcl

        manifest_formats = {
            row[0]: row[1] for row in con.execute(
                """SELECT filename,format_detected FROM capture_source_manifest
                   WHERE capture_id=?""",
                (cid,),
            )
        }
        assert manifest_formats["packetdb.sqlite"] == "packetdb", manifest_formats
        assert manifest_formats["packeteer.txt"] == "packeteer", manifest_formats

        packetdb_locators = con.execute(
            """SELECT locator_basis,details_json FROM capture_row_locators
               WHERE capture_id=? AND filename='packetdb.sqlite'
                 AND target_table='capture_raw_packets'""",
            (cid,),
        ).fetchall()
        assert len(packetdb_locators) == 1, packetdb_locators
        assert packetdb_locators[0][0] == "sqlite-row", packetdb_locators
        assert json.loads(packetdb_locators[0][1])["packetdb_packet_id"] == 1

        packetdb_chat_locators = con.execute(
            """SELECT locator_basis,details_json FROM capture_row_locators
               WHERE capture_id=? AND filename='packetdb.sqlite'
                 AND target_table='capture_chat_observations'""",
            (cid,),
        ).fetchall()
        assert len(packetdb_chat_locators) == 1, packetdb_chat_locators
        assert packetdb_chat_locators[0][0] == "sqlite-row"
        assert json.loads(packetdb_chat_locators[0][1])["packetdb_chat_id"] == 7

        npcl_targets = {
            row[0] for row in con.execute(
                """SELECT target_table FROM capture_ingest_lineage
                   WHERE capture_id=? AND filename='npclogger/tables/Test Zone.lua'""",
                (cid,),
            )
        }
        assert "capture_raw_packets" in npcl_targets, npcl_targets

        corr = packet_correlation.correlate_capture(con, cid)
        equivalents = [
            row for row in packet_correlation.list_correlations(con, cid)
            if row["basis"] == "opcode+direction+raw_bytes"
        ]
        assert len(equivalents) == 6, equivalents
        assert all(row["status"] == packet_correlation.STATUS_MATCHED for row in equivalents)
        assert corr["matched"] >= 6, corr

        # Re-ingesting the same source set must preserve one observation per source, not inflate.
        src = bci.Source(source_root)
        try:
            bci.ingest_from_source(con, cid, src, file_results=[])
        finally:
            src.close()
        assert con.execute(
            "SELECT COUNT(*) FROM capture_raw_packets WHERE capture_id=?", (cid,)
        ).fetchone()[0] == 4
        assert con.execute(
            "SELECT COUNT(*) FROM capture_chat_observations WHERE capture_id=?", (cid,)
        ).fetchone()[0] >= 1

        # Old databases receive the new nullable metadata columns without losing rows.
        old = sqlite3.connect(":memory:")
        old.execute(
            """CREATE TABLE capture_raw_packets (
                capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT, opcode TEXT, raw_hex TEXT,
                PRIMARY KEY(capture_id,seq)
            )"""
        )
        old.execute(
            "INSERT INTO capture_raw_packets VALUES (1,0,NULL,'incoming','0x00E','0E083412')"
        )
        bci.init_db(old)
        cols = {row[1] for row in old.execute("PRAGMA table_info(capture_raw_packets)")}
        assert {
            "zone_id", "packet_size", "sync_id", "is_injected", "is_blocked",
            "source_format", "source_native_id"
        } <= cols, cols
        assert old.execute(
            "SELECT COUNT(*) FROM capture_raw_packets"
        ).fetchone()[0] == 1
        old.close()

        health = capture_integrity.capture_health(con, cid)
        assert health["dimensions"]["lineage"]["exact_row_locators"] >= 4, health
        con.close()

    print("Capture packet source adapter regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
