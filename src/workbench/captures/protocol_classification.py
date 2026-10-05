"""Evidence-backed classification for reconstructed FFXI network flows.

This layer intentionally separates three claims:

1. a lobby stream can be *verified* from its framing/MD5/known command structure;
2. a later flow can be associated with an exact world or search/cache endpoint learned from a
   verified lobby ResponseNextLogin handoff;
3. that endpoint association alone does *not* prove framing or message semantics for the later
   protocol family.

No default retail/private-server port numbers are used as proof. Unknown and ambiguous flows fail
closed and retain their raw reconstructed ranges in the caller.
"""
from __future__ import annotations

from workbench.captures import lobby_ingest


def _endpoint_tuple(endpoint: dict | None) -> tuple[str, int] | None:
    if not endpoint or endpoint.get("ip") is None or endpoint.get("port") is None:
        return None
    return str(endpoint["ip"]), int(endpoint["port"])


def summarize_tcp_lifecycle(frames: list[dict]) -> dict:
    """Return transport observations without inferring application meaning."""
    syn = []
    fin = []
    rst = []
    payload = {"a_to_b": 0, "b_to_a": 0}
    for frame in frames:
        flags = frame.get("flags") or {}
        frame_no = frame.get("frame_no")
        direction = frame.get("direction")
        if flags.get("syn"):
            syn.append({"frame_no": frame_no, "direction": direction, "ack": bool(flags.get("ack"))})
        if flags.get("fin"):
            fin.append({"frame_no": frame_no, "direction": direction})
        if flags.get("rst"):
            rst.append({"frame_no": frame_no, "direction": direction})
        if direction in payload and int(frame.get("payload_len") or 0) > 0:
            payload[direction] += 1
    return {
        "syn_events": syn,
        "fin_events": fin,
        "rst_events": rst,
        "payload_frame_count_by_direction": payload,
        "certainty": "verified_observation",
        "provenance": "decoded_tcp_header_flags_and_payload_lengths",
    }


def _handoff_hints(lobby_results: list[dict]) -> list[dict]:
    hints = []
    for result in lobby_results:
        if result.get("protocol_family") != "ffxi_lobby" or not result.get("classification_validated"):
            continue
        for message in result.get("messages") or []:
            validation = message.get("validation") or {}
            if int(validation.get("command") or -1) != 0x000B:
                continue
            fields = message.get("fields") or {}
            for family, ip_key, port_key, field_name in (
                ("ffxi_world_endpoint", "server_ip", "server_port", "ResponseNextLogin.server_*"),
                ("ffxi_search_endpoint", "cache_ip", "cache_port", "ResponseNextLogin.cache_*"),
            ):
                ip = fields.get(ip_key)
                port = fields.get(port_key)
                if ip is None or port is None:
                    continue
                hints.append({
                    "protocol_family": family,
                    "endpoint": (str(ip), int(port)),
                    "certainty": "verified",
                    "provenance": field_name,
                    "source_flow_id": result.get("flow_id"),
                    "source_command": 0x000B,
                    "source_command_name": "ResponseNextLogin",
                })
    return hints


def classify_reconstructed_flows(flows: list[dict]) -> list[dict]:
    """Classify reconstructed TCP flows conservatively and correlate exact lobby handoffs.

    Search/world endpoint matches are useful classification evidence, but their payload remains
    opaque until independent framing evidence exists. If an endpoint is claimed by more than one
    family, the flow remains unknown and the candidates are reported explicitly.
    """
    lobby_results = []
    for flow in flows:
        lobby = lobby_ingest.classify_flow(flow.get("directions") or {})
        lobby_results.append({"flow_id": flow.get("flow_id"), **lobby})

    hints = _handoff_hints(lobby_results)
    out = []
    for flow, lobby in zip(flows, lobby_results):
        lifecycle = summarize_tcp_lifecycle(flow.get("frames") or [])
        if lobby.get("protocol_family") == "ffxi_lobby" and lobby.get("classification_validated"):
            out.append({
                **lobby,
                "flow_id": flow.get("flow_id"),
                "transport": flow.get("transport") or "tcp",
                "classification_scope": "framing_and_known_message_structure",
                "protocol_candidates": [{
                    "protocol_family": "ffxi_lobby",
                    "certainty": "verified",
                    "provenance": lobby.get("validation_basis"),
                }],
                "tcp_lifecycle": lifecycle,
            })
            continue

        endpoints = {
            "a": _endpoint_tuple(flow.get("endpoint_a")),
            "b": _endpoint_tuple(flow.get("endpoint_b")),
        }
        matches = []
        for hint in hints:
            for label, endpoint in endpoints.items():
                if endpoint == hint["endpoint"]:
                    matches.append({**hint, "matched_endpoint_role": label})
        families = sorted({match["protocol_family"] for match in matches})
        if len(families) == 1:
            family = families[0]
            matched = [m for m in matches if m["protocol_family"] == family]
            out.append({
                "flow_id": flow.get("flow_id"),
                "transport": flow.get("transport") or "tcp",
                "protocol_family": family,
                "classification_validated": False,
                "classification_certainty": "structurally_inferred",
                "classification_scope": "exact_endpoint_association_only_payload_opaque",
                "validation_basis": "exact_endpoint_from_verified_lobby_ResponseNextLogin",
                "protocol_candidates": matched,
                "endpoint_roles": {
                    "server": matched[0]["matched_endpoint_role"],
                    "peer": "b" if matched[0]["matched_endpoint_role"] == "a" else "a",
                },
                "role_status": "inferred_from_verified_handoff_endpoint",
                "messages": [],
                "diagnostics": lobby.get("diagnostics") or [],
                "session_phase_evidence": [],
                "decoder_status": "unknown_opaque",
                "tcp_lifecycle": lifecycle,
            })
        elif len(families) > 1:
            out.append({
                "flow_id": flow.get("flow_id"),
                "transport": flow.get("transport") or "tcp",
                "protocol_family": "unknown_tcp",
                "classification_validated": False,
                "classification_certainty": "ambiguous",
                "classification_scope": "conflicting_exact_endpoint_associations",
                "protocol_candidates": matches,
                "endpoint_roles": None,
                "role_status": "ambiguous",
                "messages": [],
                "diagnostics": (lobby.get("diagnostics") or []) + [{
                    "kind": "ambiguous_protocol_family_classification",
                    "families": families,
                    "certainty": "verified_conflict",
                }],
                "session_phase_evidence": [],
                "decoder_status": "unknown_opaque",
                "tcp_lifecycle": lifecycle,
            })
        else:
            out.append({
                **lobby,
                "flow_id": flow.get("flow_id"),
                "transport": flow.get("transport") or "tcp",
                "classification_certainty": lobby.get("classification_certainty", "unknown_opaque"),
                "classification_scope": "insufficient_evidence",
                "protocol_candidates": [],
                "tcp_lifecycle": lifecycle,
            })
    return out
