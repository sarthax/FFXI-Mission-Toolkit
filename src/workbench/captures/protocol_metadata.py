"""Post-process persisted PCAP TCP flows with conservative protocol-family metadata.

This intentionally works only inside one capture source file at a time. It reuses the exact
reconstructed ranges already persisted by PCAP ingestion and never merges flows across files or
captures.
"""
from __future__ import annotations

import json
import sqlite3

from workbench.captures import protocol_classification


_CLASSIFICATION_KEYS = (
    "protocol_family",
    "classification_validated",
    "classification_certainty",
    "classification_scope",
    "validation_basis",
    "endpoint_roles",
    "role_status",
    "protocol_candidates",
    "diagnostics",
    "session_phase_evidence",
    "decoder_status",
    "framing_evidence",
    "tcp_lifecycle",
)


def _load_flows(con: sqlite3.Connection, capture_id: int, source_file: str) -> list[dict]:
    flow_rows = con.execute(
        """SELECT flow_id,transport,endpoint_a_ip,endpoint_a_port,endpoint_b_ip,endpoint_b_port,
                  metadata_json
           FROM capture_network_flows
           WHERE capture_id=? AND source_file=?
           ORDER BY flow_id""",
        (capture_id, source_file),
    ).fetchall()
    range_rows = con.execute(
        """SELECT flow_id,direction,range_index,seq_start,seq_end,first_ts,last_ts,payload_hex,
                  frame_numbers_json,anomalies_json
           FROM capture_network_ranges
           WHERE capture_id=? AND source_file=?
           ORDER BY flow_id,direction,range_index""",
        (capture_id, source_file),
    ).fetchall()

    ranges_by_flow: dict[str, dict[str, list[dict]]] = {}
    for row in range_rows:
        flow_id, direction, range_index, seq_start, seq_end, first_ts, last_ts, payload_hex, frames_json, anomalies_json = row
        ranges_by_flow.setdefault(flow_id, {}).setdefault(direction, []).append({
            "range_index": int(range_index),
            "seq_start": int(seq_start),
            "seq_end": int(seq_end),
            "length": int(seq_end) - int(seq_start),
            "first_timestamp_seconds": first_ts,
            "last_timestamp_seconds": last_ts,
            "payload_hex": payload_hex or "",
            "frame_numbers": json.loads(frames_json or "[]"),
            "anomalies": json.loads(anomalies_json or "{}"),
        })

    flows = []
    for row in flow_rows:
        flow_id, transport, a_ip, a_port, b_ip, b_port, metadata_raw = row
        metadata = json.loads(metadata_raw or "{}")
        stored = ranges_by_flow.get(flow_id, {})
        directions = {}
        for direction in ("a_to_b", "b_to_a"):
            directions[direction] = {
                "ranges": stored.get(direction, []),
                "gaps": [],
                "retransmissions": [],
                "overlaps": [],
                "conflicting_overlaps": [],
            }
        flows.append({
            "flow_id": flow_id,
            "transport": transport or "tcp",
            "endpoint_a": {"ip": a_ip, "port": int(a_port)},
            "endpoint_b": {"ip": b_ip, "port": int(b_port)},
            "frames": metadata.get("frames") or [],
            "directions": directions,
            "_stored_metadata": metadata,
        })
    return flows


def refresh_source_flow_metadata(con: sqlite3.Connection, capture_id: int, source_file: str) -> int:
    """Merge classifier output into stored flow metadata for one exact PCAP source file."""
    flows = _load_flows(con, capture_id, source_file)
    if not flows:
        return 0

    classified = protocol_classification.classify_reconstructed_flows(flows)
    count = 0
    for flow, result in zip(flows, classified):
        metadata = dict(flow["_stored_metadata"])
        for key in _CLASSIFICATION_KEYS:
            if key in result:
                metadata[key] = result[key]
        metadata["classification_metadata_provenance"] = "same_source_file_reconstructed_flow_ranges"
        metadata["cross_source_merge_performed"] = False
        con.execute(
            """UPDATE capture_network_flows
               SET metadata_json=?
               WHERE capture_id=? AND source_file=? AND flow_id=?""",
            (json.dumps(metadata, sort_keys=True), capture_id, source_file, flow["flow_id"]),
        )
        count += 1
    return count
