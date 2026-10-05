"""Post-process persisted PCAP evidence with conservative protocol-family metadata.

This intentionally works only inside one capture source file at a time. It reuses exact persisted
TCP ranges and raw per-frame network records, and never merges flows across files or captures.
"""
from __future__ import annotations

import json
import sqlite3

from workbench.captures import map_framing, protocol_classification


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


def _map_handoff_endpoints(classified: list[dict]) -> list[dict]:
    endpoints = []
    for result in classified:
        if result.get("protocol_family") != "ffxi_lobby" or not result.get("classification_validated"):
            continue
        for message in result.get("messages") or []:
            validation = message.get("validation") or {}
            if int(validation.get("command") or -1) != 0x000B:
                continue
            fields = message.get("fields") or {}
            ip, port = fields.get("server_ip"), fields.get("server_port")
            if ip is None or port is None:
                continue
            endpoints.append({
                "endpoint": (str(ip), int(port)),
                "protocol_family": "ffxi_map_endpoint",
                "expected_transport": "udp",
                "certainty": "verified",
                "provenance": "ResponseNextLogin.server_*",
                "source_flow_id": result.get("flow_id"),
            })
    return endpoints


def _annotate_udp_handoffs(
    con: sqlite3.Connection,
    capture_id: int,
    source_file: str,
    map_endpoints: list[dict],
) -> int:
    if not map_endpoints:
        return 0
    rows = con.execute(
        """SELECT record_key,payload_json
           FROM capture_structured_records
           WHERE capture_id=? AND source_file=? AND family='pcap_network'""",
        (capture_id, source_file),
    ).fetchall()
    updated = 0
    for record_key, payload_raw in rows:
        payload = json.loads(payload_raw or "{}")
        if payload.get("transport") != "udp":
            continue
        observed = {
            "src": (payload.get("src_ip"), payload.get("src_port")),
            "dst": (payload.get("dst_ip"), payload.get("dst_port")),
        }
        matches = []
        for hint in map_endpoints:
            for side, endpoint in observed.items():
                if endpoint[0] is None or endpoint[1] is None:
                    continue
                if (str(endpoint[0]), int(endpoint[1])) == hint["endpoint"]:
                    matches.append({
                        **hint,
                        "matched_endpoint_side": side,
                    })
        if not matches:
            continue

        payload["protocol_family"] = "ffxi_map_endpoint"
        payload["classification_validated"] = False
        payload["classification_certainty"] = "structurally_inferred"
        payload["classification_scope"] = "exact_udp_endpoint_from_verified_lobby_ResponseNextLogin"
        payload["validation_basis"] = "transport_compatible_exact_endpoint_from_verified_lobby_handoff"
        payload["protocol_candidates"] = matches
        payload["decoder_status"] = "raw_udp_payload_preserved"
        payload["classification_metadata_provenance"] = "same_source_file_lobby_handoff_to_udp_frame"
        payload["cross_source_merge_performed"] = False

        raw_hex = payload.get("transport_payload_hex") or ""
        try:
            raw_payload = bytes.fromhex(raw_hex) if raw_hex else b""
        except ValueError:
            raw_payload = b""
        handshake = map_framing.inspect_login_datagram(raw_payload)
        endpoint_is_destination = any(match["matched_endpoint_side"] == "dst" for match in matches)
        probe_diagnostics = list(handshake["diagnostics"])
        if handshake["recognized"] and not endpoint_is_destination:
            probe_diagnostics.append({
                "kind": "map_login_direction_mismatch",
                "expected_server_endpoint_side": "dst",
                "observed_server_endpoint_sides": sorted({match["matched_endpoint_side"] for match in matches}),
                "certainty": "verified_conflict",
            })

        payload["map_handshake_probe"] = {
            "recognized": bool(handshake["recognized"] and endpoint_is_destination),
            "message_type": handshake["message_type"],
            "certainty": handshake["certainty"] if endpoint_is_destination else "ambiguous",
            "validation_basis": handshake["validation_basis"],
            "diagnostics": probe_diagnostics,
            "field_evidence": handshake["field_evidence"],
            "direction_basis": "client_0x000A_requires_verified_map_endpoint_as_udp_destination",
        }
        if handshake["recognized"] and endpoint_is_destination:
            payload["classification_validated"] = True
            payload["classification_certainty"] = "verified"
            payload["classification_scope"] = "verified_lobby_handoff_plus_verified_map_0x000A_udp_handshake"
            payload["validation_basis"] = "exact_verified_map_endpoint_and_source_backed_0x000A_structure_and_direction"
            payload["decoder_status"] = handshake["decoder_status"]
            payload["framing_evidence"] = {
                "protocol_family": "ffxi_map",
                "message_type": handshake["message_type"],
                "certainty": "verified",
                "direction": "client_to_map",
                "validation_basis": handshake["validation_basis"],
                "field_evidence": handshake["field_evidence"],
                "opaque_inner_hex": handshake["opaque_inner_hex"],
            }

        con.execute(
            """UPDATE capture_structured_records
               SET payload_json=?
               WHERE capture_id=? AND source_file=? AND family='pcap_network' AND record_key=?""",
            (json.dumps(payload, sort_keys=True), capture_id, source_file, record_key),
        )
        updated += 1
    return updated


def refresh_source_flow_metadata(con: sqlite3.Connection, capture_id: int, source_file: str) -> int:
    """Merge classifier output into same-source TCP flow metadata and correlate map UDP endpoints."""
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

    _annotate_udp_handoffs(
        con,
        capture_id,
        source_file,
        _map_handoff_endpoints(classified),
    )
    return count
