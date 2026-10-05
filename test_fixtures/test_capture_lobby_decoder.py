#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import struct

import build_capture_index
from workbench.captures import lobby_ingest, protocol_classification


CLIENT_IP = (10, 0, 0, 2)
SERVER_IP = (203, 0, 113, 10)
CLIENT_PORT = 40000
SERVER_PORT = 54001


def lobby_packet(command: int, body: bytes) -> bytes:
    size = 28 + len(body)
    packet = bytearray(size)
    struct.pack_into("<III", packet, 0, size, 0x46465849, command)
    packet[28:] = body
    packet[12:28] = b"\x00" * 16
    packet[12:28] = hashlib.md5(packet).digest()
    return bytes(packet)


def ipv4_tcp_frame(payload: bytes, *, sport: int, dport: int, seq: int, src, dst, flags: int = 0x18) -> bytes:
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
    tcp[13] = flags
    struct.pack_into("!H", tcp, 14, 65535)
    return eth + bytes(ip) + bytes(tcp) + payload


def make_pcap(frames):
    out = bytearray()
    out += b"\xd4\xc3\xb2\xa1"
    out += struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)
    for sec, usec, frame in frames:
        out += struct.pack("<IIII", sec, usec, len(frame), len(frame))
        out += frame
    return bytes(out)


def encode_ip_u32(ip):
    packed = bytes(ip)
    return struct.unpack("<I", packed)[0]


def _empty_direction():
    return {"ranges": [], "gaps": [], "retransmissions": [], "overlaps": [], "conflicting_overlaps": []}


def _single_range_direction(payload: bytes, seq: int):
    return {
        "ranges": [{
            "seq_start": seq,
            "seq_end": seq + len(payload),
            "length": len(payload),
            "payload_hex": payload.hex().upper(),
            "frame_numbers": [1],
            "first_timestamp_seconds": 1.0,
            "last_timestamp_seconds": 1.0,
        }],
        "gaps": [], "retransmissions": [], "overlaps": [], "conflicting_overlaps": [],
    }


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    cid = build_capture_index.create_manual_capture(con, "lobby tcp", "Research", None)

    # C->S RequestQueryWorldList (0x24, fixed 0x2C)
    req_worlds = lobby_packet(0x0024, b"\x00" * 16)
    assert len(req_worlds) == 0x2C

    # S->C ResponseKey (0x05, fixed 0x28) with wardrobes 3-8 enabled.
    response_key = lobby_packet(
        0x0005,
        struct.pack("<III", 0x11223344, 0x00000FFF, 0x000000FD),
    )
    assert len(response_key) == 0x28

    # S->C ResponseNextLogin (0x0B, fixed 0x48)
    body = bytearray()
    body += struct.pack("<I", 0x01020304)
    body += struct.pack("<I", 0x00081234)
    body += b"Testchar\x00" + b"\x00" * 7
    body += struct.pack("<I", 2)
    body += struct.pack("<I", encode_ip_u32((11, 22, 33, 44)))
    body += struct.pack("<I", 54230)
    body += struct.pack("<I", encode_ip_u32((55, 66, 77, 88)))
    body += struct.pack("<I", 54002)
    next_login = lobby_packet(0x000B, bytes(body))
    assert len(next_login) == 0x48

    # A separate flow with IXFF + known command but invalid MD5 must remain unknown_tcp.
    false_packet = bytearray(req_worlds)
    false_packet[12] ^= 0xFF

    frames = [
        # Split request across two TCP segments to ensure classification happens after reassembly.
        (1_700_000_000, 100_000, ipv4_tcp_frame(
            req_worlds[:17], sport=CLIENT_PORT, dport=SERVER_PORT, seq=1000,
            src=CLIENT_IP, dst=SERVER_IP,
        )),
        (1_700_000_000, 200_000, ipv4_tcp_frame(
            req_worlds[17:], sport=CLIENT_PORT, dport=SERVER_PORT, seq=1017,
            src=CLIENT_IP, dst=SERVER_IP,
        )),
        # Two valid server responses back-to-back across separate segments.
        (1_700_000_000, 300_000, ipv4_tcp_frame(
            response_key, sport=SERVER_PORT, dport=CLIENT_PORT, seq=5000,
            src=SERVER_IP, dst=CLIENT_IP,
        )),
        (1_700_000_000, 400_000, ipv4_tcp_frame(
            next_login[:31], sport=SERVER_PORT, dport=CLIENT_PORT, seq=5000 + len(response_key),
            src=SERVER_IP, dst=CLIENT_IP,
        )),
        (1_700_000_000, 500_000, ipv4_tcp_frame(
            next_login[31:], sport=SERVER_PORT, dport=CLIENT_PORT,
            seq=5000 + len(response_key) + 31,
            src=SERVER_IP, dst=CLIENT_IP,
        )),
        # False-positive candidate on another TCP flow/port.
        (1_700_000_001, 100_000, ipv4_tcp_frame(
            bytes(false_packet), sport=41000, dport=65000, seq=9000,
            src=CLIENT_IP, dst=SERVER_IP,
        )),
    ]

    pcap = make_pcap(frames)
    result = build_capture_index.ingest_single_file(con, cid, "lobby-session.pcap", pcap)
    assert result["format"] == "pcap", result
    assert result["error"] is None, result

    flows = con.execute(
        """SELECT flow_id,endpoint_a_ip,endpoint_a_port,endpoint_b_ip,endpoint_b_port,metadata_json
           FROM capture_network_flows
           WHERE capture_id=? AND source_file='lobby-session.pcap'
           ORDER BY flow_id""",
        (cid,),
    ).fetchall()
    assert len(flows) == 2, flows

    lobby_flow = next(row for row in flows if row[2] == CLIENT_PORT and row[4] == SERVER_PORT)
    lobby_meta = json.loads(lobby_flow[5])
    assert lobby_meta["protocol_family"] == "ffxi_lobby", lobby_meta
    assert lobby_meta["classification_validated"] is True, lobby_meta
    assert lobby_meta["endpoint_roles"] == {"client": "a", "server": "b"}, lobby_meta
    assert lobby_meta["role_status"] == "validated_from_command_direction", lobby_meta

    false_flow = next(row for row in flows if row[2] == 41000)
    false_meta = json.loads(false_flow[5])
    assert false_meta["protocol_family"] == "unknown_tcp", false_meta
    assert false_meta["classification_validated"] is False, false_meta

    messages = con.execute(
        """SELECT direction,command,command_name,validation_status,fields_json,provenance_json
           FROM capture_network_messages
           WHERE capture_id=? AND source_file='lobby-session.pcap'
           ORDER BY command""",
        (cid,),
    ).fetchall()
    assert len(messages) == 3, messages
    assert {row[1] for row in messages} == {0x0005, 0x000B, 0x0024}, messages
    assert all(row[3] == "MD5_VALID" for row in messages), messages

    key_msg = next(row for row in messages if row[1] == 0x0005)
    key_fields = json.loads(key_msg[4])
    assert key_msg[0] == "b_to_a", key_msg
    assert key_fields["md5_key"] == 0x11223344, key_fields
    assert key_fields["features"]["security_token"] is True, key_fields
    assert key_fields["features"]["wardrobe3"] is True, key_fields
    assert key_fields["features"]["wardrobe4"] is True, key_fields
    assert key_fields["features"]["wardrobe5"] is True, key_fields
    assert key_fields["features"]["wardrobe6"] is True, key_fields
    assert key_fields["features"]["wardrobe7"] is True, key_fields
    assert key_fields["features"]["wardrobe8"] is True, key_fields

    next_msg = next(row for row in messages if row[1] == 0x000B)
    next_fields = json.loads(next_msg[4])
    assert next_fields["character_name"] == "Testchar", next_fields
    assert next_fields["server_ip"] == "11.22.33.44", next_fields
    assert next_fields["server_port"] == 54230, next_fields
    assert next_fields["cache_ip"] == "55.66.77.88", next_fields
    assert next_fields["cache_port"] == 54002, next_fields

    # Evidence metadata and framing diagnostics remain separate from decoded semantics.
    decoded_next = lobby_ingest.decode_packet(next_login)
    assert decoded_next["field_evidence"]["server_ip"]["certainty"] == "verified", decoded_next
    resync = lobby_ingest.scan_range_detailed(b"\xAA\xBB" + next_login, 7000)
    assert len(resync["messages"]) == 1, resync
    assert any(d["kind"] == "framing_resynchronization" for d in resync["diagnostics"]), resync
    truncated = lobby_ingest.scan_range_detailed(next_login[:40], 8000)
    assert truncated["messages"] == [], truncated
    assert any(d["kind"] == "truncated_frame_candidate" for d in truncated["diagnostics"]), truncated

    # Exact handoff endpoints can classify later flows without decoding their opaque payloads.
    research_lobby_flow = {
        "flow_id": "research-lobby",
        "endpoint_a": {"ip": "10.0.0.2", "port": 40000},
        "endpoint_b": {"ip": "203.0.113.10", "port": 54001},
        "transport": "tcp",
        "frames": [],
        "directions": {
            "a_to_b": _empty_direction(),
            "b_to_a": _single_range_direction(next_login, 9000),
        },
    }
    world_flow = {
        "flow_id": "world-handoff",
        "endpoint_a": {"ip": "10.0.0.2", "port": 41000},
        "endpoint_b": {"ip": "11.22.33.44", "port": 54230},
        "transport": "tcp",
        "frames": [],
        "directions": {
            "a_to_b": _single_range_direction(b"opaque-world", 10000),
            "b_to_a": _empty_direction(),
        },
    }
    search_flow = {
        "flow_id": "search-handoff",
        "endpoint_a": {"ip": "10.0.0.2", "port": 42000},
        "endpoint_b": {"ip": "55.66.77.88", "port": 54002},
        "transport": "tcp",
        "frames": [],
        "directions": {
            "a_to_b": _single_range_direction(b"opaque-search", 11000),
            "b_to_a": _empty_direction(),
        },
    }
    classified = {row["flow_id"]: row for row in protocol_classification.classify_reconstructed_flows(
        [research_lobby_flow, world_flow, search_flow]
    )}
    assert classified["research-lobby"]["protocol_family"] == "ffxi_lobby", classified
    assert classified["world-handoff"]["protocol_family"] == "ffxi_world_endpoint", classified
    assert classified["world-handoff"]["classification_validated"] is False, classified
    assert classified["world-handoff"]["decoder_status"] == "unknown_opaque", classified
    assert classified["search-handoff"]["protocol_family"] == "ffxi_search_endpoint", classified
    assert classified["search-handoff"]["classification_scope"] == "exact_endpoint_association_only_payload_opaque", classified

    req_msg = next(row for row in messages if row[1] == 0x0024)
    assert req_msg[0] == "a_to_b", req_msg
    req_prov = json.loads(req_msg[5])
    assert req_prov["md5_valid"] is True, req_prov
    assert req_prov["command_direction"] == "c2s", req_prov
    assert req_prov["frame_numbers"] == [1, 2], req_prov
    assert req_prov["sensitive_field_policy"].startswith("raw_packet_retained"), req_prov

    # Invalid-MD5 traffic must never become a decoded lobby message.
    assert con.execute(
        """SELECT COUNT(*) FROM capture_network_messages
           WHERE capture_id=? AND flow_id=?""",
        (cid, false_flow[0]),
    ).fetchone()[0] == 0

    locators = con.execute(
        """SELECT locator_basis,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename='lobby-session.pcap'
             AND target_table='capture_network_messages'
           ORDER BY row_key""",
        (cid,),
    ).fetchall()
    assert len(locators) == 3, locators
    assert all(row[0] == "pcap-tcp-message" for row in locators), locators
    assert all(json.loads(row[1])["md5_valid"] is True for row in locators), locators

    # Reingestion remains idempotent.
    again = build_capture_index.ingest_single_file(con, cid, "lobby-session.pcap", pcap)
    assert again["error"] is None, again
    assert con.execute(
        """SELECT COUNT(*) FROM capture_network_messages
           WHERE capture_id=? AND source_file='lobby-session.pcap'""",
        (cid,),
    ).fetchone()[0] == 3

    con.close()
    print("Validated lobby TCP classifier/decoder regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
