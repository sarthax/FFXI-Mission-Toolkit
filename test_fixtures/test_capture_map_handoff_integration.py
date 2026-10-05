#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import struct

import build_capture_index
from workbench.captures import map_framing


CLIENT_IP = (10, 0, 0, 2)
LOBBY_IP = (198, 51, 100, 5)
MAP_IP = (11, 22, 33, 44)
LOBBY_CLIENT_PORT = 40000
LOBBY_SERVER_PORT = 54001
MAP_CLIENT_PORT = 43000
MAP_SERVER_PORT = 54230


def lobby_packet(command: int, body: bytes) -> bytes:
    size = 28 + len(body)
    packet = bytearray(size)
    struct.pack_into("<III", packet, 0, size, 0x46465849, command)
    packet[28:] = body
    packet[12:28] = b"\x00" * 16
    packet[12:28] = hashlib.md5(packet).digest()
    return bytes(packet)


def encode_ip_u32(ip) -> int:
    return struct.unpack("<I", bytes(ip))[0]


def response_next_login() -> bytes:
    body = bytearray()
    body += struct.pack("<I", 0x01020304)
    body += struct.pack("<I", 0x00081234)
    body += b"Researcher\x00" + b"\x00" * 5
    body += struct.pack("<I", 7)
    body += struct.pack("<I", encode_ip_u32(MAP_IP))
    body += struct.pack("<I", MAP_SERVER_PORT)
    body += struct.pack("<I", encode_ip_u32((55, 66, 77, 88)))
    body += struct.pack("<I", 54002)
    packet = lobby_packet(0x000B, bytes(body))
    assert len(packet) == 0x48
    return packet


def map_login_datagram() -> bytes:
    inner = bytearray(map_framing.LOGIN_PACKET_SIZE)
    header = map_framing.LOGIN_OPCODE | ((map_framing.LOGIN_PACKET_SIZE // 4) << 9)
    struct.pack_into("<H", inner, 0, header)
    struct.pack_into("<H", inner, 2, 0x1234)
    for i in range(map_framing.LOGIN_PACKET_CHECK_SUM_START, map_framing.LOGIN_PACKET_SIZE):
        inner[i] = (i * 13 + 9) & 0xFF
    inner[map_framing.LOGIN_PACKET_CHECK_OFFSET] = (
        sum(inner[map_framing.LOGIN_PACKET_CHECK_SUM_START:map_framing.LOGIN_PACKET_SIZE]) & 0xFF
    )
    trailer = hashlib.md5(inner).digest()
    return bytes(bytearray(map_framing.FFXI_HEADER_SIZE) + inner + trailer)


def ipv4_tcp_frame(payload: bytes, *, sport: int, dport: int, seq: int, src, dst) -> bytes:
    eth = bytes.fromhex("00112233445566778899AABB0800")
    total_len = 20 + 20 + len(payload)
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, total_len)
    ip[8] = 64
    ip[9] = 6
    ip[12:16] = bytes(src)
    ip[16:20] = bytes(dst)
    tcp = bytearray(20)
    struct.pack_into("!HHII", tcp, 0, sport, dport, seq, 0)
    tcp[12] = 5 << 4
    tcp[13] = 0x18
    struct.pack_into("!H", tcp, 14, 65535)
    return eth + bytes(ip) + bytes(tcp) + payload


def ipv4_udp_frame(payload: bytes, *, sport: int, dport: int, src, dst) -> bytes:
    eth = bytes.fromhex("00112233445566778899AABB0800")
    total_len = 20 + 8 + len(payload)
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, total_len)
    ip[8] = 64
    ip[9] = 17
    ip[12:16] = bytes(src)
    ip[16:20] = bytes(dst)
    udp = bytearray(8)
    struct.pack_into("!HHHH", udp, 0, sport, dport, 8 + len(payload), 0)
    return eth + bytes(ip) + bytes(udp) + payload


def make_pcap(frames) -> bytes:
    out = bytearray(b"\xd4\xc3\xb2\xa1")
    out += struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)
    for sec, usec, frame in frames:
        out += struct.pack("<IIII", sec, usec, len(frame), len(frame))
        out += frame
    return bytes(out)


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    cid = build_capture_index.create_manual_capture(con, "map handshake", "Research", None)

    handoff = response_next_login()
    map_login = map_login_datagram()
    assert len(map_login) == map_framing.MIN_DATAGRAM_SIZE
    frames = [
        (1_700_000_000, 100_000, ipv4_tcp_frame(
            handoff,
            sport=LOBBY_SERVER_PORT,
            dport=LOBBY_CLIENT_PORT,
            seq=5000,
            src=LOBBY_IP,
            dst=CLIENT_IP,
        )),
        (1_700_000_000, 200_000, ipv4_udp_frame(
            map_login,
            sport=MAP_CLIENT_PORT,
            dport=MAP_SERVER_PORT,
            src=CLIENT_IP,
            dst=MAP_IP,
        )),
        # Same structurally valid bytes in the reverse direction must not become a verified
        # client-zone-login observation because the verified map endpoint is the source.
        (1_700_000_000, 300_000, ipv4_udp_frame(
            map_login,
            sport=MAP_SERVER_PORT,
            dport=MAP_CLIENT_PORT,
            src=MAP_IP,
            dst=CLIENT_IP,
        )),
    ]

    result = build_capture_index.ingest_single_file(con, cid, "map-handshake.pcap", make_pcap(frames))
    assert result["error"] is None, result

    rows = con.execute(
        """SELECT payload_json FROM capture_structured_records
           WHERE capture_id=? AND source_file='map-handshake.pcap'
             AND family='pcap_network' AND record_type='UDP'
           ORDER BY record_key""",
        (cid,),
    ).fetchall()
    assert len(rows) == 2, rows
    decoded = [json.loads(row[0]) for row in rows]

    forward = next(row for row in decoded if row["dst_ip"] == "11.22.33.44")
    assert forward["protocol_family"] == "ffxi_map_endpoint", forward
    assert forward["classification_validated"] is True, forward
    assert forward["classification_certainty"] == "verified", forward
    assert forward["classification_scope"] == "verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake", forward
    assert forward["framing_evidence"]["message_type"] == "client_zone_login_0x000A", forward
    assert forward["framing_evidence"]["direction"] == "client_to_map", forward
    assert forward["map_handshake_probe"]["recognized"] is True, forward
    assert forward["map_handshake_probe"]["field_evidence"]["outer_md5"]["valid"] is True, forward
    assert forward["map_handshake_probe"]["field_evidence"]["LoginPacketCheck"]["valid"] is True, forward
    assert forward["transport_payload_hex"] == map_login.hex().upper(), forward
    assert forward["cross_source_merge_performed"] is False, forward

    reverse = next(row for row in decoded if row["src_ip"] == "11.22.33.44")
    assert reverse["protocol_family"] == "ffxi_map_endpoint", reverse
    assert reverse["classification_validated"] is False, reverse
    assert reverse["classification_certainty"] == "structurally_inferred", reverse
    assert reverse["map_handshake_probe"]["recognized"] is False, reverse
    assert any(
        d["kind"] == "map_login_direction_mismatch"
        for d in reverse["map_handshake_probe"]["diagnostics"]
    ), reverse
    assert reverse["transport_payload_hex"] == map_login.hex().upper(), reverse

    # Reingestion remains deterministic and does not duplicate network records.
    again = build_capture_index.ingest_single_file(con, cid, "map-handshake.pcap", make_pcap(frames))
    assert again["error"] is None, again
    assert con.execute(
        """SELECT COUNT(*) FROM capture_structured_records
           WHERE capture_id=? AND source_file='map-handshake.pcap'
             AND family='pcap_network' AND record_type='UDP'""",
        (cid,),
    ).fetchone()[0] == 2

    con.close()
    print("Map handoff/0x000A PCAP integration regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
