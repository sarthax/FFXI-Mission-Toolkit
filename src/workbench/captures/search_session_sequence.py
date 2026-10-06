"""Deterministic same-flow search/cache request-response sequencing.

This layer never compares TCP sequence numbers across directions and never pairs by timestamp.
Cross-direction order is promoted only when reconstructed-range capture-frame provenance proves that
one interval finished before another began. Missing/gapped/conflicting client->server evidence makes
rolling search state unsafe, so automatic outbound decryption fails closed for that flow.
"""
from __future__ import annotations

from copy import deepcopy

from workbench.captures import (
    search_crypto_envelope,
    search_response_decode,
    search_response_evidence,
)


def _directions(server_role: str) -> tuple[str | None, str | None]:
    if server_role == "a":
        return "b_to_a", "a_to_b"
    if server_role == "b":
        return "a_to_b", "b_to_a"
    return None, None


def _capture_interval(frame: dict) -> tuple[int, int] | None:
    provenance = frame.get("range_provenance") or {}
    first = provenance.get("frame_number_min")
    last = provenance.get("frame_number_max")
    if first is None or last is None:
        return None
    return int(first), int(last)


def _client_stream_blockers(directions: dict, client_to_server: str) -> list[dict]:
    """Return evidence-loss conditions that could hide a state-changing inbound request."""
    summary = directions.get(client_to_server) or {}
    blockers: list[dict] = []
    for gap in summary.get("gaps") or []:
        blockers.append({"kind": "client_stream_gap_blocks_search_state_sequence", "gap": gap})
    for conflict in summary.get("conflicting_overlaps") or []:
        blockers.append({
            "kind": "client_stream_conflicting_overlap_blocks_search_state_sequence",
            "conflict": conflict,
        })
    for index, rr in enumerate(summary.get("ranges") or []):
        if rr.get("gap_before"):
            blockers.append({
                "kind": "client_range_gap_before_blocks_search_state_sequence",
                "range_index": index,
                "seq_start": rr.get("seq_start"),
            })
        anomalies = rr.get("anomalies") or {}
        if anomalies.get("conflicting_overlaps"):
            blockers.append({
                "kind": "client_range_conflict_blocks_search_state_sequence",
                "range_index": index,
                "count": len(anomalies.get("conflicting_overlaps") or []),
            })
    return blockers


def sequence_validated_session(scanned: dict, directions: dict, server_role: str) -> dict:
    """Pair and decode server responses only when capture provenance proves predecessor order.

    `scanned` should already have passed `search_framing.resolve_crypto_direction()`, so validated
    client frames contain `inbound_decryption` and `validated_request`. The returned structure is a
    deep copy; the caller's framing evidence is not mutated.
    """
    result = deepcopy(scanned)
    result["session_sequence"] = {
        "automatic_pairing_performed": False,
        "ordering_basis": "capture_frame_interval_strict_before_only",
        "timestamps_used_for_pairing": False,
        "tcp_sequence_compared_across_directions": False,
        "server_role": server_role,
        "pairs": [],
        "diagnostics": [],
    }
    seq_meta = result["session_sequence"]
    client_to_server, server_to_client = _directions(server_role)
    if client_to_server is None:
        seq_meta["diagnostics"].append({"kind": "search_sequence_server_role_unresolved"})
        return result

    blockers = _client_stream_blockers(directions, client_to_server)
    if blockers:
        seq_meta["diagnostics"].extend(blockers)
        seq_meta["status"] = "blocked_by_client_stream_integrity"
        return result

    frames = result.get("frames") or []
    inbound_frames = [f for f in frames if f.get("direction") == client_to_server]
    outbound_frames = [f for f in frames if f.get("direction") == server_to_client]

    # Same-direction application order is available from reconstructed byte order. Capture-frame
    # intervals are used only to prove the cross-direction boundary.
    inbound_frames.sort(key=lambda f: (int(f.get("range_index") or 0), int(f.get("frame_index") or 0), int(f.get("seq_start") or 0)))
    outbound_frames.sort(key=lambda f: (int((_capture_interval(f) or (1 << 62, 1 << 62))[0]), int(f.get("range_index") or 0), int(f.get("frame_index") or 0)))

    for outbound in outbound_frames:
        out_interval = _capture_interval(outbound)
        pair = {
            "outbound_range_index": outbound.get("range_index"),
            "outbound_frame_index": outbound.get("frame_index"),
            "outbound_seq_start": outbound.get("seq_start"),
            "outbound_capture_interval": list(out_interval) if out_interval else None,
            "paired": False,
            "certainty": "unknown_opaque",
            "diagnostics": [],
        }
        if out_interval is None:
            pair["diagnostics"].append({"kind": "outbound_capture_frame_provenance_missing"})
            seq_meta["pairs"].append(pair)
            continue

        out_first = out_interval[0]
        prior: list[dict] = []
        overlapping: list[dict] = []
        missing_provenance = False
        for inbound in inbound_frames:
            interval = _capture_interval(inbound)
            if interval is None:
                missing_provenance = True
                continue
            if interval[1] < out_first:
                prior.append(inbound)
            elif interval[0] <= out_first <= interval[1]:
                overlapping.append(inbound)

        if missing_provenance:
            pair["diagnostics"].append({"kind": "inbound_capture_frame_provenance_missing"})
        if overlapping:
            pair["diagnostics"].append({
                "kind": "cross_direction_order_unresolved",
                "reason": "inbound_range_capture_interval_overlaps_outbound_start",
                "overlapping_inbound_frames": [
                    {
                        "range_index": item.get("range_index"),
                        "frame_index": item.get("frame_index"),
                        "capture_interval": list(_capture_interval(item) or ()),
                    }
                    for item in overlapping
                ],
            })
        if missing_provenance or overlapping or not prior:
            if not prior:
                pair["diagnostics"].append({"kind": "no_proven_inbound_predecessor"})
            seq_meta["pairs"].append(pair)
            continue

        predecessor = prior[-1]
        # A later observed inbound candidate that failed validation is still state-significant: the
        # server may have accepted bytes we cannot prove, so do not fall back to an earlier request.
        if not predecessor.get("decryption_validated"):
            pair["diagnostics"].append({
                "kind": "latest_proven_inbound_predecessor_not_validated",
                "range_index": predecessor.get("range_index"),
                "frame_index": predecessor.get("frame_index"),
            })
            seq_meta["pairs"].append(pair)
            continue

        inbound_wire_hex = predecessor.get("raw_hex") or ""
        inbound_decrypted_hex = ((predecessor.get("inbound_decryption") or {}).get("decrypted_hex") or "")
        outbound_wire_hex = outbound.get("raw_hex") or ""
        if not inbound_wire_hex or not inbound_decrypted_hex or not outbound_wire_hex:
            pair["diagnostics"].append({"kind": "search_sequence_required_bytes_missing"})
            seq_meta["pairs"].append(pair)
            continue

        state = search_crypto_envelope.derive_outbound_state(
            bytes.fromhex(inbound_wire_hex), bytes.fromhex(inbound_decrypted_hex)
        )
        if not state.get("validated"):
            pair["diagnostics"].append({
                "kind": "search_sequence_predecessor_state_derivation_failed",
                "state_diagnostics": state.get("diagnostics") or [],
            })
            seq_meta["pairs"].append(pair)
            continue

        outbound_crypto = search_crypto_envelope.decrypt_outbound_frame(bytes.fromhex(outbound_wire_hex), state)
        pair.update({
            "paired": True,
            "certainty": "verified_capture_frame_interval_predecessor",
            "predecessor_range_index": predecessor.get("range_index"),
            "predecessor_frame_index": predecessor.get("frame_index"),
            "predecessor_seq_start": predecessor.get("seq_start"),
            "predecessor_capture_interval": list(_capture_interval(predecessor) or ()),
            "predecessor_request_type": predecessor.get("validated_packet_type"),
            "predecessor_request_type_name": predecessor.get("validated_packet_type_name"),
            "state_evidence": state,
            "outbound_crypto": outbound_crypto,
        })
        outbound["session_predecessor"] = {
            "range_index": predecessor.get("range_index"),
            "frame_index": predecessor.get("frame_index"),
            "capture_interval": list(_capture_interval(predecessor) or ()),
            "certainty": pair["certainty"],
        }
        outbound["outbound_decryption"] = outbound_crypto

        if outbound_crypto.get("validated"):
            structural = search_response_decode.decode_validated_outbound(
                outbound_crypto, predecessor.get("validated_request")
            )
            evidence = search_response_evidence.apply_evidence_policy(
                structural, predecessor.get("validated_request")
            )
            pair["response"] = evidence
            outbound["validated_response"] = evidence
        else:
            pair["diagnostics"].append({
                "kind": "paired_outbound_crypto_validation_failed",
                "crypto_diagnostics": outbound_crypto.get("diagnostics") or [],
            })
        seq_meta["pairs"].append(pair)

    seq_meta["automatic_pairing_performed"] = any(item.get("paired") for item in seq_meta["pairs"])
    seq_meta["status"] = "sequenced_with_strict_capture_order" if seq_meta["automatic_pairing_performed"] else "no_safe_pairs"
    return result
