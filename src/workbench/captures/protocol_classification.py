"""Evidence-backed classification for reconstructed FFXI network flows.

This layer intentionally separates four claims:

1. a lobby stream can be *verified* from its framing/MD5/known command structure;
2. a later endpoint can be associated with an exact map or search/cache handoff learned from a
   verified lobby ResponseNextLogin;
3. endpoint association is transport-sensitive and does not by itself prove protocol semantics;
4. search/cache framing candidates may be recognized from source-backed clear-header structure,
   but only after an exact verified search handoff association.

Modern LandSandBoat fills ResponseNextLogin.server_* from the selected zone endpoint, which is the
map/game UDP service. Therefore a reconstructed TCP flow matching that IP/port is not promoted to a
world/map TCP family. The endpoint match is retained as evidence with a transport-mismatch diagnostic.

No default retail/private-server port numbers are used as proof. Unknown and ambiguous flows fail
closed and retain their raw reconstructed ranges in the caller.
"""
from __future__ import annotations

from workbench.captures import lobby_ingest, search_framing


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
            for family, transport, ip_key, port_key, field_name in (
                ("ffxi_map_endpoint", "udp", "server_ip", "server_port", "ResponseNextLogin.server_*"),
                ("ffxi_search_endpoint", "tcp", "cache_ip", "cache_port", "ResponseNextLogin.cache_*"),
            ):
                ip = fields.get(ip_key)
                port = fields.get(port_key)
                if ip is None or port is None:
                    continue
                hints.append({
                    "protocol_family": family,
                    "expected_transport": transport,
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

    Only transport-compatible handoff evidence can classify a reconstructed flow. Search TCP flows
    may gain source-backed framing and crypto-envelope evidence from their clear length/IXFF header
    while the encrypted payload remains undecoded. A map/game handoff learned from modern LSB is UDP
    evidence and therefore cannot promote a TCP flow even when IP/port happen to match.
    """
    lobby_results = []
    for flow in flows:
        lobby = lobby_ingest.classify_flow(flow.get("directions") or {})
        lobby_results.append({"flow_id": flow.get("flow_id"), **lobby})

    hints = _handoff_hints(lobby_results)
    out = []
    for flow, lobby in zip(flows, lobby_results):
        transport = flow.get("transport") or "tcp"
        lifecycle = summarize_tcp_lifecycle(flow.get("frames") or [])
        if lobby.get("protocol_family") == "ffxi_lobby" and lobby.get("classification_validated"):
            out.append({
                **lobby,
                "flow_id": flow.get("flow_id"),
                "transport": transport,
                "classification_scope": "framing_and_known_message_structure",
                "protocol_candidates": [{
                    "protocol_family": "ffxi_lobby",
                    "expected_transport": "tcp",
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

        compatible = [m for m in matches if m.get("expected_transport") == transport]
        incompatible = [m for m in matches if m.get("expected_transport") != transport]
        families = sorted({match["protocol_family"] for match in compatible})
        transport_diagnostics = [{
            "kind": "handoff_endpoint_transport_not_proven",
            "protocol_family": match["protocol_family"],
            "observed_transport": transport,
            "expected_transport": match.get("expected_transport"),
            "endpoint": {"ip": match["endpoint"][0], "port": match["endpoint"][1]},
            "certainty": "verified_endpoint_transport_mismatch",
        } for match in incompatible]

        if len(families) == 1:
            family = families[0]
            matched = [m for m in compatible if m["protocol_family"] == family]
            diagnostics = list(lobby.get("diagnostics") or []) + transport_diagnostics
            framing_evidence = None
            classification_scope = "exact_transport_compatible_endpoint_association_only_payload_opaque"
            decoder_status = "unknown_opaque"

            if family == "ffxi_search_endpoint":
                scanned = search_framing.scan_directions(flow.get("directions") or {})
                scanned = search_framing.resolve_crypto_direction(scanned, matched[0]["matched_endpoint_role"])
                diagnostics.extend(scanned["diagnostics"])
                if scanned["frames"]:
                    framing_evidence = {
                        "family": "ffxi_search",
                        "frame_count": len(scanned["frames"]),
                        "frames": scanned["frames"],
                        "certainty": "structurally_inferred",
                        "provenance": "LandSandBoat SearchHandler clear framing plus source-backed crypto envelope",
                        "payload_semantics": "unknown_opaque",
                    }
                    classification_scope = "verified_search_handoff_plus_source_backed_search_framing"
                    decoder_status = "encrypted_or_opaque"

            out.append({
                "flow_id": flow.get("flow_id"),
                "transport": transport,
                "protocol_family": family,
                "classification_validated": False,
                "classification_certainty": "structurally_inferred",
                "classification_scope": classification_scope,
                "validation_basis": "exact_transport_compatible_endpoint_from_verified_lobby_ResponseNextLogin",
                "protocol_candidates": compatible + incompatible,
                "endpoint_roles": {
                    "server": matched[0]["matched_endpoint_role"],
                    "peer": "b" if matched[0]["matched_endpoint_role"] == "a" else "a",
                },
                "role_status": "inferred_from_verified_handoff_endpoint_and_transport",
                "messages": [],
                "diagnostics": diagnostics,
                "session_phase_evidence": [],
                "decoder_status": decoder_status,
                "framing_evidence": framing_evidence,
                "tcp_lifecycle": lifecycle,
            })
        elif len(families) > 1:
            out.append({
                "flow_id": flow.get("flow_id"),
                "transport": transport,
                "protocol_family": "unknown_tcp",
                "classification_validated": False,
                "classification_certainty": "ambiguous",
                "classification_scope": "conflicting_transport_compatible_endpoint_associations",
                "protocol_candidates": compatible + incompatible,
                "endpoint_roles": None,
                "role_status": "ambiguous",
                "messages": [],
                "diagnostics": (lobby.get("diagnostics") or []) + transport_diagnostics + [{
                    "kind": "ambiguous_protocol_family_classification",
                    "families": families,
                    "certainty": "verified_conflict",
                }],
                "session_phase_evidence": [],
                "decoder_status": "unknown_opaque",
                "framing_evidence": None,
                "tcp_lifecycle": lifecycle,
            })
        elif incompatible:
            out.append({
                **lobby,
                "flow_id": flow.get("flow_id"),
                "transport": transport,
                "protocol_family": "unknown_tcp",
                "classification_validated": False,
                "classification_certainty": "unknown_opaque",
                "classification_scope": "handoff_endpoint_transport_mismatch",
                "protocol_candidates": incompatible,
                "endpoint_roles": None,
                "role_status": "transport_not_proven",
                "messages": [],
                "diagnostics": (lobby.get("diagnostics") or []) + transport_diagnostics,
                "session_phase_evidence": [],
                "decoder_status": "unknown_opaque",
                "framing_evidence": None,
                "tcp_lifecycle": lifecycle,
            })
        else:
            out.append({
                **lobby,
                "flow_id": flow.get("flow_id"),
                "transport": transport,
                "classification_certainty": lobby.get("classification_certainty", "unknown_opaque"),
                "classification_scope": "insufficient_evidence",
                "protocol_candidates": [],
                "framing_evidence": None,
                "tcp_lifecycle": lifecycle,
            })
    return out
