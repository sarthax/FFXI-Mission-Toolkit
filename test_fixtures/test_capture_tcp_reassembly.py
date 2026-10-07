#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import struct

from workbench.captures.ingestion import build_index as build_capture_index


def ipv4_tcp_frame(
    payload: bytes,
    *,
    sport: int,
    dport: int,
    seq: int,
    ack: int = 0,
    flags: int = 0x18,
    src=(10, 0, 0, 2),
    dst=(203, 0, 113, 10),
) -> bytes:
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
    struct.pack_into("!HHII", tcp, 0, sport, dport, seq, ack)
    tcp[12] = 5 << 4
    tcp[13] = flags
    struct.pack_into("!H", tcp, 14, 65535)
    return eth + bytes(ip) + bytes(tcp) + payload


def make_pcap(frames: list[tuple[int, int, bytes]]) -> bytes:
    out = bytearray()
    out += b"\xd4\xc3\xb2\xa1"
    out += struct.pack("<HHIIII", 2, 4, 0, 0, 65535, 1)
    for sec, usec, frame in frames:
        out += struct.pack("<IIII", sec, usec, len(frame), len(frame))
        out += frame
    return bytes(out)


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    cid = build_capture_index.create_manual_capture(con, "tcp reassembly", "Research", None)

    # A->B:
    #   seq 1000: ABCD
    #   seq 1004: EFGH
    #   seq 1004: EFGH  (exact retransmit)
    #   seq 1006: GHXY  (overlap, conflicting bytes at 1008/1009)
    #   seq 1012: MN    (gap 1010-1011)
    # B->A:
    #   seq 5000: pong
    frames = [
        (1_700_000_000, 100_000, ipv4_tcp_frame(b"ABCD", sport=40000, dport=54001, seq=1000)),
        (1_700_000_000, 200_000, ipv4_tcp_frame(b"EFGHIJ", sport=40000, dport=54001, seq=1004)),
        (1_700_000_000, 300_000, ipv4_tcp_frame(b"EFGHIJ", sport=40000, dport=54001, seq=1004)),
        (1_700_000_000, 400_000, ipv4_tcp_frame(b"GHXY", sport=40000, dport=54001, seq=1006)),
        (1_700_000_000, 500_000, ipv4_tcp_frame(b"MN", sport=40000, dport=54001, seq=1012)),
        (1_700_000_000, 600_000, ipv4_tcp_frame(
            b"pong", sport=54001, dport=40000, seq=5000,
            src=(203, 0, 113, 10), dst=(10, 0, 0, 2)
        )),
    ]
    pcap = make_pcap(frames)

    result = build_capture_index.ingest_single_file(con, cid, "tcp-session.pcap", pcap)
    assert result["format"] == "pcap", result
    assert result["error"] is None, result
    assert result["rows"] == 10, result  # 6 frames + 1 flow + 3 reconstructed ranges

    flows = con.execute(
        """SELECT flow_id,endpoint_a_ip,endpoint_a_port,endpoint_b_ip,endpoint_b_port,
                  frame_count,payload_frame_count,metadata_json
           FROM capture_network_flows
           WHERE capture_id=? AND source_file='tcp-session.pcap'""",
        (cid,),
    ).fetchall()
    assert len(flows) == 1, flows
    flow_id, a_ip, a_port, b_ip, b_port, frame_count, payload_count, meta_raw = flows[0]
    assert (a_ip, a_port) == ("10.0.0.2", 40000), flows[0]
    assert (b_ip, b_port) == ("203.0.113.10", 54001), flows[0]
    assert frame_count == 6 and payload_count == 6, flows[0]
    meta = json.loads(meta_raw)
    a = meta["direction_summaries"]["a_to_b"]
    assert a["gap_count"] == 1, a
    assert a["gaps"] == [{"length": 2, "seq_end": 1012, "seq_start": 1010}], a
    assert a["retransmission_count"] == 1, a
    assert a["overlap_count"] == 2, a
    assert a["conflicting_overlap_count"] == 2, a
    assert meta["protocol_family"] == "unknown_tcp", meta
    assert meta["endpoint_role_basis"] == "canonical_endpoint_sort_only", meta

    ranges = con.execute(
        """SELECT direction,range_index,seq_start,seq_end,payload_hex,
                  frame_numbers_json,anomalies_json
           FROM capture_network_ranges
           WHERE capture_id=? AND source_file='tcp-session.pcap'
           ORDER BY direction,range_index""",
        (cid,),
    ).fetchall()
    assert len(ranges) == 3, ranges

    a_ranges = [r for r in ranges if r[0] == "a_to_b"]
    b_ranges = [r for r in ranges if r[0] == "b_to_a"]
    assert len(a_ranges) == 2 and len(b_ranges) == 1, ranges
    assert (a_ranges[0][2], a_ranges[0][3]) == (1000, 1010), a_ranges[0]
    # First observed bytes win; conflicting XY does not overwrite bytes already seen.
    assert bytes.fromhex(a_ranges[0][4]) == b"ABCDEFGHIJ", a_ranges[0]
    assert (a_ranges[1][2], a_ranges[1][3], bytes.fromhex(a_ranges[1][4])) == (1012, 1014, b"MN"), a_ranges[1]
    assert (b_ranges[0][2], b_ranges[0][3], bytes.fromhex(b_ranges[0][4])) == (5000, 5004, b"pong"), b_ranges[0]

    anomalies = json.loads(a_ranges[0][6])
    assert anomalies["missing_bytes_fabricated"] is False, anomalies
    assert anomalies["byte_selection_rule"] == "first_observed_byte_wins_conflicts_recorded", anomalies
    assert len(anomalies["retransmissions"]) == 1, anomalies
    assert len(anomalies["conflicting_overlaps"]) == 2, anomalies

    locators = con.execute(
        """SELECT target_table,locator_basis,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename='tcp-session.pcap'
             AND target_table IN ('capture_network_flows','capture_network_ranges')
           ORDER BY target_table,row_key""",
        (cid,),
    ).fetchall()
    assert len(locators) == 4, locators
    assert {r[1] for r in locators} == {"pcap-flow", "pcap-tcp-range"}, locators
    range_details = [json.loads(r[2]) for r in locators if r[0] == "capture_network_ranges"]
    assert all(d["frame_numbers"] for d in range_details), range_details

    # Reingestion replaces source-owned flows/ranges instead of duplicating them.
    again = build_capture_index.ingest_single_file(con, cid, "tcp-session.pcap", pcap)
    assert again["error"] is None, again
    assert con.execute(
        """SELECT COUNT(*) FROM capture_network_flows
           WHERE capture_id=? AND source_file='tcp-session.pcap'""",
        (cid,),
    ).fetchone()[0] == 1
    assert con.execute(
        """SELECT COUNT(*) FROM capture_network_ranges
           WHERE capture_id=? AND source_file='tcp-session.pcap'""",
        (cid,),
    ).fetchone()[0] == 3

    con.close()
    print("PCAP TCP flow reconstruction regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
