#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index as bci
import youtube_chat_ocr
from workbench.core.services import pcap_ingest


def ethernet_ipv4_udp(payload: bytes, src_port: int = 40000, dst_port: int = 54230) -> bytes:
    eth = bytes.fromhex("00112233445566778899AABB0800")
    src_ip = bytes([10, 0, 0, 2])
    dst_ip = bytes([10, 0, 0, 3])
    udp_len = 8 + len(payload)
    udp = struct.pack("!HHHH", src_port, dst_port, udp_len, 0) + payload
    total = 20 + len(udp)
    ipv4 = (
        bytes([0x45, 0x00])
        + struct.pack("!H", total)
        + b"\x00\x01\x00\x00\x40\x11\x00\x00"
        + src_ip + dst_ip
    )
    return eth + ipv4 + udp


def classic_pcap(frame: bytes) -> bytes:
    header = struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    record = struct.pack("<IIII", 100, 500000, len(frame), len(frame)) + frame
    return header + record


def pcapng(frame: bytes) -> bytes:
    def block(block_type: int, body: bytes) -> bytes:
        pad = (-len(body)) % 4
        body = body + (b"\x00" * pad)
        total = 12 + len(body)
        return struct.pack("<II", block_type, total) + body + struct.pack("<I", total)

    shb_body = struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)
    idb_body = struct.pack("<HHI", 1, 0, 65535)
    # 100.5 seconds at default microsecond resolution.
    ticks = 100_500_000
    epb_body = struct.pack("<IIIII", 0, ticks >> 32, ticks & 0xFFFFFFFF, len(frame), len(frame)) + frame
    return block(0x0A0D0D0A, shb_body) + block(1, idb_body) + block(6, epb_body)


def make_packetdb(path: Path):
    con = sqlite3.connect(path)
    con.executescript(
        """CREATE TABLE PACKETS (
             PACKET_ID INTEGER PRIMARY KEY,
             RECEIVED_DT DATETIME NOT NULL,
             DIRECTION INTEGER NOT NULL,
             ZONE_ID INTEGER,
             PACKET_TYPE INTEGER NOT NULL,
             PACKET_SIZE INTEGER NOT NULL,
             PACKET_SYNC INTEGER NOT NULL,
             PACKET_DATA TEXT NOT NULL
           );
           CREATE TABLE CHATLOG (
             CHAT_ID INTEGER PRIMARY KEY,
             RECEIVED_DT DATETIME NOT NULL,
             DIRECTION INTEGER NOT NULL,
             ZONE_ID INTEGER,
             CHAT_TEXT TEXT NOT NULL
           );"""
    )
    con.execute(
        "INSERT INTO PACKETS VALUES (?,?,?,?,?,?,?,?)",
        (1, "2026-09-28 12:00:00", 0, 75, 0x00E, 16, 0x1234,
         "0E083412AABBCCDD0000000000000000"),
    )
    con.execute(
        "INSERT INTO CHATLOG VALUES (?,?,?,?,?)",
        (7, "2026-09-28 12:00:01", 0, 75, "A system message from PacketDB"),
    )
    con.commit()
    con.close()


WHOLE_SESSION_SIMPLE = """INCOMING < CS Event + Params (0x034): NPC: 16982179 (Sorrowful Sage)
Event: 278
Params: 1,2,3
Option: 0
Message: 42

"""


def main():
    # Capturebar's documented default rendering should become structured OCR fields.
    capturebar_text = (
        "[75]Bhaflau Remnants - Archaic Gear (12.5,-3.0,7.25) "
        "R(128) (WAR99/DNC49) Moon: 87% Waxing Gibbous"
    )
    parsed = youtube_chat_ocr.parse_capture_line(
        youtube_chat_ocr.CAPTURE_PROFILE_CAPTUREBAR, capturebar_text
    )
    assert parsed["capturebar"]["zone_id"] == 75, parsed
    assert parsed["capturebar"]["zone_name"] == "Bhaflau Remnants", parsed
    assert parsed["capturebar"]["x"] == 12.5 and parsed["capturebar"]["z"] == -3.0, parsed
    assert parsed["capturebar"]["rotation"] == 128, parsed
    assert parsed["capturebar"]["main_job"] == "WAR", parsed
    assert parsed["capturebar"]["moon_phase"] == "Waxing Gibbous", parsed
    profiles = youtube_chat_ocr.load_layout_profiles()
    assert profiles["capturebar_overlay"]["regions"][0]["capture_profile"] == "capturebar"

    frame = ethernet_ipv4_udp(b"FFXI-NETWORK-EVIDENCE")
    assert pcap_ingest.sniff_format(classic_pcap(frame)) == "pcap"
    assert pcap_ingest.sniff_format(pcapng(frame)) == "pcapng"

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        source.mkdir()
        make_packetdb(source / "packetdb.sqlite")
        (source / "eventview").mkdir()
        (source / "eventview" / "simple.log").write_text(WHOLE_SESSION_SIMPLE, encoding="utf-8")
        (source / "network.pcap").write_bytes(classic_pcap(frame))
        (source / "network.pcapng").write_bytes(pcapng(frame))
        (source / "stattrack.csv").write_text(
            "timestamp,hpmax,mpmax,mjob_no,mjob_lv,sjob_no,sjob_lv,STR,DEX,VIT,AGI,INT,MND,CHR\n"
            "2026-09-28 12:00:02,2000,500,1,99,19,49,120,110,115,100,90,95,88\n",
            encoding="utf-8",
        )

        con = sqlite3.connect(root / "capture.db")
        bci.init_db(con)
        cid = bci.create_manual_capture(con, "next-wave fixture", "Research", None)
        src = bci.Source(source)
        results = []
        try:
            counts = bci.ingest_from_source(con, cid, src, file_results=results)
        finally:
            src.close()

        failures = [r for r in results if r["error"]]
        assert not failures, failures

        chats = con.execute(
            """SELECT ts,direction,zone_id,text,source_format,source_native_id
               FROM capture_chat_observations WHERE capture_id=?""", (cid,)
        ).fetchall()
        assert len(chats) == 1, chats
        assert chats[0][1] == "incoming" and chats[0][2] == 75, chats
        assert chats[0][3] == "A system message from PacketDB", chats
        assert chats[0][4] == "packetdb" and chats[0][5].endswith(":chat:7"), chats

        chat_locator = con.execute(
            """SELECT locator_basis,details_json FROM capture_row_locators
               WHERE capture_id=? AND filename='packetdb.sqlite'
                 AND target_table='capture_chat_observations'""", (cid,)
        ).fetchone()
        assert chat_locator and chat_locator[0] == "sqlite-row", chat_locator
        assert json.loads(chat_locator[1])["packetdb_chat_id"] == 7

        unknown = con.execute(
            """SELECT zone_db,event_hex,message_id FROM capture_events
               WHERE capture_id=? AND zone_db=?""", (cid, bci.UNKNOWN_ZONE_DB)
        ).fetchall()
        assert len(unknown) == 1, unknown
        assert unknown[0][1] == "0x0116" and unknown[0][2] == 42, unknown

        network = con.execute(
            """SELECT source_format,src_ip,dst_ip,src_port,dst_port,transport,
                      payload_hex,service_hint
               FROM capture_network_observations WHERE capture_id=? ORDER BY source_format""",
            (cid,),
        ).fetchall()
        assert len(network) == 2, network
        assert {r[0] for r in network} == {"pcap", "pcapng"}, network
        for row in network:
            assert row[1:6] == ("10.0.0.2", "10.0.0.3", 40000, 54230, "UDP"), row
            assert bytes.fromhex(row[6]) == b"FFXI-NETWORK-EVIDENCE", row
            assert "54230:zone/map" in row[7], row

        assert counts["chat"] == 1, counts
        assert counts["network"] == 2, counts
        stat = con.execute(
            """SELECT family,ts,payload_json FROM capture_structured_records
               WHERE capture_id=? AND family='stattrack_csv'""", (cid,)
        ).fetchone()
        assert stat and stat[0] == "stattrack_csv", stat
        assert stat[1] == "2026-09-28 12:00:02", stat
        assert json.loads(stat[2])["hpmax"] == "2000", stat

        # Safe re-ingest reuses source-native IDs and does not inflate observations.
        src = bci.Source(source)
        try:
            bci.ingest_from_source(con, cid, src, file_results=[])
        finally:
            src.close()
        assert con.execute(
            "SELECT COUNT(*) FROM capture_chat_observations WHERE capture_id=?", (cid,)
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM capture_network_observations WHERE capture_id=?", (cid,)
        ).fetchone()[0] == 2

        con.close()

    print("Capture next-wave ingestion regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
