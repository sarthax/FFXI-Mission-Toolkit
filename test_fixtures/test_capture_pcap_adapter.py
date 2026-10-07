#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import struct

from workbench.captures.ingestion import build_index as build_capture_index


FFXI_CHUNK = bytes.fromhex("0E 08 34 12 AA BB CC DD 00 00 00 00 00 00 00 00")


def ipv4_udp_frame(payload: bytes, *, sport: int = 54001, dport: int = 54230) -> bytes:
    eth = bytes.fromhex("00112233445566778899AABB0800")
    total_len = 20 + 8 + len(payload)
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, total_len)
    ip[8] = 64
    ip[9] = 17
    ip[12:16] = bytes([10, 0, 0, 2])
    ip[16:20] = bytes([203, 0, 113, 10])
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0)
    return eth + bytes(ip) + udp + payload


def make_pcap(frames: list[tuple[int, int, bytes]]) -> bytes:
    out = bytearray()
    out += b"\xd4\xc3\xb2\xa1"
    out += struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)
    for sec, usec, frame in frames:
        out += struct.pack("<IIII", sec, usec, len(frame), len(frame))
        out += frame
    return bytes(out)


def _ng_block(block_type: int, body: bytes) -> bytes:
    size = 12 + len(body)
    if size % 4:
        body += b"\x00" * (4 - (size % 4))
        size = 12 + len(body)
    return struct.pack("<II", block_type, size) + body + struct.pack("<I", size)


def make_pcapng(frame: bytes) -> bytes:
    shb = _ng_block(
        0x0A0D0D0A,
        b"\x4d\x3c\x2b\x1a" + struct.pack("<HHq", 1, 0, -1),
    )
    idb_body = struct.pack("<HHI", 1, 0, 65535)
    # if_tsresol option: code=9, len=1, value=6 (microseconds), padded to 4 bytes; end option.
    idb_body += struct.pack("<HHB", 9, 1, 6) + b"\x00\x00\x00" + struct.pack("<HH", 0, 0)
    idb = _ng_block(1, idb_body)
    ticks = 1_700_000_000_250_000
    epb_body = struct.pack(
        "<IIIII",
        0,
        (ticks >> 32) & 0xFFFFFFFF,
        ticks & 0xFFFFFFFF,
        len(frame),
        len(frame),
    )
    epb_body += frame
    if len(frame) % 4:
        epb_body += b"\x00" * (4 - len(frame) % 4)
    epb = _ng_block(6, epb_body)
    return shb + idb + epb


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    cid = build_capture_index.create_manual_capture(con, "pcap adapter", "Research", None)

    good_frame = ipv4_udp_frame(FFXI_CHUNK)
    opaque_frame = ipv4_udp_frame(b"\x99\x88\x77\x66\x55\x44\x33\x22")
    pcap = make_pcap([
        (1_700_000_000, 125_000, good_frame),
        (1_700_000_001, 500_000, opaque_frame),
    ])

    result = build_capture_index.ingest_single_file(con, cid, "retail-session.pcap", pcap)
    assert result["format"] == "pcap", result
    assert result["error"] is None, result
    assert result["rows"] == 3, result  # 2 network frames + 1 proven plaintext FFXI chunk

    structured = con.execute(
        """SELECT record_key,record_type,ts,payload_json
           FROM capture_structured_records
           WHERE capture_id=? AND family='pcap_network'
           ORDER BY CAST(record_key AS INTEGER)""",
        (cid,),
    ).fetchall()
    assert len(structured) == 2, structured
    first = json.loads(structured[0][3])
    assert structured[0][1] == "UDP", structured[0]
    assert first["src_ip"] == "10.0.0.2" and first["dst_ip"] == "203.0.113.10", first
    assert first["src_port"] == 54001 and first["dst_port"] == 54230, first
    assert first["transport_payload_hex"] == FFXI_CHUNK.hex().upper(), first
    assert first["captured_frame_hex"] == good_frame.hex().upper(), first

    raw = con.execute(
        """SELECT ts,direction,opcode,raw_hex,packet_size,sync_id,source_format,source_native_id
           FROM capture_raw_packets
           WHERE capture_id=? AND source_format='pcap_plaintext_chunk'""",
        (cid,),
    ).fetchall()
    assert len(raw) == 1, raw
    assert raw[0][0] == "2023-11-14T22:13:20.125000Z", raw
    assert raw[0][1] == "unknown", raw
    assert raw[0][2].lower() == "0x00e", raw
    assert raw[0][3] == FFXI_CHUNK.hex().upper(), raw
    assert raw[0][4] == 16 and raw[0][5] == 0x1234, raw
    assert ":frame:1:chunk:0" in raw[0][7], raw

    # The opaque/encrypted-looking datagram must remain as frame evidence without guessed chunks.
    second = json.loads(structured[1][3])
    assert second["transport_payload_hex"] == opaque_frame[-8:].hex().upper(), second
    assert con.execute(
        """SELECT COUNT(*) FROM capture_raw_packets
           WHERE capture_id=? AND source_format='pcap_plaintext_chunk'""",
        (cid,),
    ).fetchone()[0] == 1

    locators = con.execute(
        """SELECT target_table,locator_basis,start_offset,end_offset
           FROM capture_row_locators
           WHERE capture_id=? AND filename='retail-session.pcap'
           ORDER BY target_table,row_key""",
        (cid,),
    ).fetchall()
    assert len(locators) == 3, locators
    assert {row[1] for row in locators} == {"pcap-frame"}, locators
    assert all(row[2] is not None and row[3] > row[2] for row in locators), locators

    # PCAPNG follows the same evidence contract.
    pcapng = make_pcapng(good_frame)
    result_ng = build_capture_index.ingest_single_file(con, cid, "session.pcapng", pcapng)
    assert result_ng["format"] == "pcapng", result_ng
    assert result_ng["rows"] == 2, result_ng
    ng_frame = con.execute(
        """SELECT payload_json FROM capture_structured_records
           WHERE capture_id=? AND source_file='session.pcapng' AND family='pcap_network'""",
        (cid,),
    ).fetchone()
    assert ng_frame, "PCAPNG frame missing"
    ng_payload = json.loads(ng_frame[0])
    assert ng_payload["pcap_format"] == "pcapng", ng_payload
    assert ng_payload["interface_id"] == 0, ng_payload

    # Reingestion is idempotent for both frame and promoted-chunk evidence.
    again = build_capture_index.ingest_single_file(con, cid, "retail-session.pcap", pcap)
    assert again["rows"] == 3, again
    assert con.execute(
        """SELECT COUNT(*) FROM capture_structured_records
           WHERE capture_id=? AND source_file='retail-session.pcap'
             AND family='pcap_network'""",
        (cid,),
    ).fetchone()[0] == 2
    assert con.execute(
        """SELECT COUNT(*) FROM capture_raw_packets
           WHERE capture_id=? AND source_format='pcap_plaintext_chunk'
             AND source_native_id LIKE 'retail-session.pcap:%'""",
        (cid,),
    ).fetchone()[0] == 1

    manifest = dict(con.execute(
        """SELECT filename,format_detected FROM capture_source_manifest
           WHERE capture_id=? AND filename IN ('retail-session.pcap','session.pcapng')""",
        (cid,),
    ).fetchall())
    assert manifest == {
        "retail-session.pcap": "pcap",
        "session.pcapng": "pcapng",
    }, manifest

    con.close()
    print("PCAP/PCAPNG capture adapter regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
