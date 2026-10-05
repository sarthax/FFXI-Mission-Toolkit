#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import lobby_ingest
from workbench.captures import protocol_classification
from workbench.captures import search_framing


def lobby_packet(command: int, size: int, body_writer=None) -> bytes:
    packet = bytearray(size)
    struct.pack_into("<I", packet, 0, size)
    packet[4:8] = b"IXFF"
    struct.pack_into("<I", packet, 8, command)
    if body_writer:
        body_writer(packet)
    work = bytearray(packet)
    work[12:28] = b"\x00" * 16
    packet[12:28] = hashlib.md5(work).digest()
    return bytes(packet)


def response_next_login(*, server=(203, 0, 113, 10), server_port=54230,
                        cache=(203, 0, 113, 11), cache_port=54002) -> bytes:
    def write(packet: bytearray):
        struct.pack_into("<II", packet, 28, 0x10000001, 0x20000002)
        packet[36:52] = b"Researcher\x00" + b"\x00" * 5
        struct.pack_into("<I", packet, 52, 7)
        packet[56:60] = bytes(server)
        struct.pack_into("<I", packet, 60, server_port)
        packet[64:68] = bytes(cache)
        struct.pack_into("<I", packet, 68, cache_port)
    return lobby_packet(0x000B, 0x48, write)


def search_frame(size=32, fill=0xA5) -> bytes:
    packet = bytearray([fill] * size)
    struct.pack_into("<H", packet, 0, size)
    packet[2:4] = b"\x00\x00"
    packet[4:8] = b"IXFF"
    return bytes(packet)


def directions(payload: bytes, seq=1000):
    return {
        "a_to_b": {"ranges": [], "gaps": [], "retransmissions": [], "overlaps": [], "conflicting_overlaps": []},
        "b_to_a": {
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
        },
    }


def flow(flow_id: str, a, b, dirs=None, frames=None):
    return {
        "flow_id": flow_id,
        "endpoint_a": {"ip": a[0], "port": a[1]},
        "endpoint_b": {"ip": b[0], "port": b[1]},
        "transport": "tcp",
        "directions": dirs or directions(b""),
        "frames": frames or [],
    }


def main():
    packet = response_next_login()
    decoded = lobby_ingest.decode_packet(packet)
    assert decoded["validation"]["valid"] is True, decoded
    assert decoded["field_evidence"]["server_ip"]["certainty"] == "verified", decoded

    prefixed = b"\x99\x98\x97" + packet
    scanned = lobby_ingest.scan_range_detailed(prefixed, 4000)
    assert len(scanned["messages"]) == 1, scanned
    assert any(d["kind"] == "framing_resynchronization" for d in scanned["diagnostics"]), scanned
    assert scanned["messages"][0]["seq_start"] == 4003, scanned

    truncated = packet[:40]
    truncated_scan = lobby_ingest.scan_range_detailed(truncated, 5000)
    assert truncated_scan["messages"] == [], truncated_scan
    assert any(d["kind"] == "truncated_frame_candidate" for d in truncated_scan["diagnostics"]), truncated_scan
    assert truncated_scan["diagnostics"][0]["raw_slice_hex"], truncated_scan

    unknown = bytearray(32)
    struct.pack_into("<I", unknown, 0, 32)
    unknown[4:8] = b"IXFF"
    struct.pack_into("<I", unknown, 8, 0xDEAD)
    unknown_scan = lobby_ingest.scan_range_detailed(bytes(unknown), 6000)
    assert any(d["kind"] == "unknown_message_type" for d in unknown_scan["diagnostics"]), unknown_scan

    sf = search_frame()
    search_scan = search_framing.scan_range(b"\xFE\xED" + sf, 7000)
    assert len(search_scan["frames"]) == 1, search_scan
    assert search_scan["frames"][0]["seq_start"] == 7002, search_scan
    assert search_scan["frames"][0]["declared_size"] == len(sf), search_scan
    assert search_scan["frames"][0]["decoder_status"] == "encrypted_or_opaque", search_scan
    assert search_scan["frames"][0]["opaque_payload_hex"] == sf[8:].hex().upper(), search_scan
    assert any(d["kind"] == "framing_resynchronization" for d in search_scan["diagnostics"]), search_scan
    truncated_search = search_framing.scan_range(sf[:-3], 8000)
    assert truncated_search["frames"] == [], truncated_search
    assert any(d["kind"] == "truncated_frame_candidate" for d in truncated_search["diagnostics"]), truncated_search

    lobby_flow = flow(
        "lobby",
        ("10.0.0.2", 40000),
        ("198.51.100.5", 54001),
        directions(packet),
        [{"frame_no": 1, "direction": "b_to_a", "payload_len": len(packet),
          "flags": {"syn": False, "ack": True, "fin": False, "rst": False}}],
    )
    map_tcp_flow = flow(
        "map-tcp",
        ("10.0.0.2", 41000),
        ("203.0.113.10", 54230),
        directions(b"opaque-world-bytes", 9000),
        [{"frame_no": 2, "direction": "a_to_b", "payload_len": 18,
          "flags": {"syn": False, "ack": True, "fin": False, "rst": False}}],
    )
    search_flow = flow(
        "search",
        ("10.0.0.2", 42000),
        ("203.0.113.11", 54002),
        directions(sf, 10000),
    )
    unknown_flow = flow(
        "other",
        ("10.0.0.2", 43000),
        ("192.0.2.55", 12345),
        directions(b"opaque", 11000),
    )
    signature_only_flow = flow(
        "signature-only",
        ("10.0.0.2", 43001),
        ("192.0.2.56", 12346),
        directions(sf, 11500),
    )
    results = {r["flow_id"]: r for r in protocol_classification.classify_reconstructed_flows(
        [lobby_flow, map_tcp_flow, search_flow, unknown_flow, signature_only_flow]
    )}
    assert results["lobby"]["protocol_family"] == "ffxi_lobby", results["lobby"]
    assert results["lobby"]["classification_certainty"] == "verified", results["lobby"]
    # ResponseNextLogin.server_* is a zone/map UDP handoff in modern LSB; an exact TCP endpoint
    # match must therefore remain unknown rather than being promoted to a world/map TCP family.
    assert results["map-tcp"]["protocol_family"] == "unknown_tcp", results["map-tcp"]
    assert results["map-tcp"]["classification_scope"] == "handoff_endpoint_transport_mismatch", results["map-tcp"]
    assert any(d["kind"] == "handoff_endpoint_transport_not_proven" for d in results["map-tcp"]["diagnostics"]), results["map-tcp"]
    assert results["map-tcp"]["protocol_candidates"][0]["protocol_family"] == "ffxi_map_endpoint", results["map-tcp"]
    assert results["map-tcp"]["protocol_candidates"][0]["expected_transport"] == "udp", results["map-tcp"]

    assert results["search"]["protocol_family"] == "ffxi_search_endpoint", results["search"]
    assert results["search"]["classification_scope"] == "verified_search_handoff_plus_source_backed_search_framing", results["search"]
    assert results["search"]["decoder_status"] == "encrypted_or_opaque", results["search"]
    assert results["search"]["framing_evidence"]["frame_count"] == 1, results["search"]
    assert results["search"]["framing_evidence"]["payload_semantics"] == "unknown_opaque", results["search"]
    assert results["other"]["protocol_family"] == "unknown_tcp", results["other"]
    assert results["other"]["protocol_candidates"] == [], results["other"]
    assert results["signature-only"]["protocol_family"] == "unknown_tcp", results["signature-only"]
    assert results["signature-only"]["classification_scope"] == "insufficient_evidence", results["signature-only"]

    # When map and search handoff endpoints are numerically identical, transport resolves the TCP
    # path: search is compatible; map remains a preserved transport-mismatch candidate.
    same = response_next_login(server=(203, 0, 113, 20), server_port=55000,
                               cache=(203, 0, 113, 20), cache_port=55000)
    same_results = protocol_classification.classify_reconstructed_flows([
        flow("lobby2", ("10.0.0.2", 44000), ("198.51.100.5", 54001), directions(same)),
        flow("same-endpoint", ("10.0.0.2", 45000), ("203.0.113.20", 55000), directions(sf, 12000)),
    ])
    same_endpoint = next(r for r in same_results if r["flow_id"] == "same-endpoint")
    assert same_endpoint["protocol_family"] == "ffxi_search_endpoint", same_endpoint
    assert same_endpoint["framing_evidence"]["frame_count"] == 1, same_endpoint
    assert any(c["protocol_family"] == "ffxi_map_endpoint" and c["expected_transport"] == "udp"
               for c in same_endpoint["protocol_candidates"]), same_endpoint
    assert any(d["kind"] == "handoff_endpoint_transport_not_proven" for d in same_endpoint["diagnostics"]), same_endpoint

    print("Capture protocol classification regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
