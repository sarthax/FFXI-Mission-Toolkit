"""Source-backed framing observations for FFXI search/cache TCP streams.

LandSandBoat's search server leaves packet length at offset 0 and IXFF at offsets 4..7 clear. The
payload from offset 8 is encrypted on the wire. Framing candidates are recognized conservatively;
actual inbound decryption is attempted only after a higher layer proves which endpoint is the search
server from a verified lobby handoff.
"""
from __future__ import annotations

import struct

from workbench.captures import search_crypto_envelope

SEARCH_MIN_FRAME_SIZE = 28
SEARCH_MARKER = b"IXFF"
SEARCH_MAX_FRAME_SIZE = 0xFFFF


def scan_range(payload: bytes, seq_start: int = 0) -> dict:
    """Recover source-backed search frame candidates from one contiguous TCP byte range."""
    frames: list[dict] = []
    diagnostics: list[dict] = []
    pos = 0
    skipped_start: int | None = None

    while pos < len(payload):
        remaining = len(payload) - pos
        if remaining < 8:
            if remaining:
                diagnostics.append({
                    "kind": "opaque_trailing_bytes",
                    "range_offset": pos,
                    "seq_start": seq_start + pos,
                    "length": remaining,
                    "raw_slice_hex": payload[pos:].hex().upper(),
                    "certainty": "verified_observation",
                })
            break

        declared = struct.unpack_from("<H", payload, pos)[0]
        marker = payload[pos + 4:pos + 8]
        plausible = SEARCH_MIN_FRAME_SIZE <= declared <= SEARCH_MAX_FRAME_SIZE and marker == SEARCH_MARKER
        if not plausible:
            if skipped_start is None:
                skipped_start = pos
            pos += 1
            continue

        if skipped_start is not None:
            diagnostics.append({
                "kind": "framing_resynchronization",
                "range_offset": skipped_start,
                "seq_start": seq_start + skipped_start,
                "skipped_length": pos - skipped_start,
                "raw_slice_hex": payload[skipped_start:pos].hex().upper(),
                "certainty": "structurally_inferred",
            })
            skipped_start = None

        end = pos + declared
        if end > len(payload):
            diagnostics.append({
                "kind": "truncated_frame_candidate",
                "range_offset": pos,
                "seq_start": seq_start + pos,
                "declared_size": declared,
                "observed_size": len(payload) - pos,
                "raw_slice_hex": payload[pos:].hex().upper(),
                "certainty": "structurally_inferred",
            })
            break

        raw = payload[pos:end]
        frames.append({
            "range_offset": pos,
            "seq_start": seq_start + pos,
            "seq_end": seq_start + end,
            "declared_size": declared,
            "marker": "IXFF",
            "raw_hex": raw.hex().upper(),
            "clear_header_hex": raw[:8].hex().upper(),
            "opaque_payload_hex": raw[8:].hex().upper(),
            "framing_certainty": "structurally_inferred",
            "framing_provenance": "LandSandBoat SearchHandler read_func/encrypt clear length+IXFF",
            "decoder_status": "encrypted_or_opaque",
            "crypto_envelope": search_crypto_envelope.inspect_frame(raw),
        })
        pos = end

    return {"frames": frames, "diagnostics": diagnostics}


def scan_directions(directions: dict[str, dict]) -> dict:
    """Scan reconstructed ranges in both directions without assigning endpoint roles."""
    frames: list[dict] = []
    diagnostics: list[dict] = []
    for direction in ("a_to_b", "b_to_a"):
        for range_index, rr in enumerate((directions.get(direction) or {}).get("ranges") or []):
            payload_hex = rr.get("payload_hex") or ""
            payload = bytes.fromhex(payload_hex) if payload_hex else b""
            scanned = scan_range(payload, int(rr.get("seq_start") or 0))
            for frame_index, frame in enumerate(scanned["frames"]):
                frames.append({
                    "direction": direction,
                    "range_index": range_index,
                    "frame_index": frame_index,
                    **frame,
                })
            for diagnostic in scanned["diagnostics"]:
                diagnostics.append({
                    "direction": direction,
                    "range_index": range_index,
                    **diagnostic,
                })
    return {"frames": frames, "diagnostics": diagnostics}


def resolve_crypto_direction(scanned: dict, server_role: str) -> dict:
    """Resolve and, for proven inbound frames only, execute the search crypto contract.

    `server_role` is `a` or `b` from the reconstructed flow. The operation mutates the supplied
    scan result in-place. Outbound frames are never decrypted here because LSB server encryption
    depends on rolling key state from a previously decrypted inbound request.
    """
    if server_role not in {"a", "b"}:
        return scanned
    client_to_server = "b_to_a" if server_role == "a" else "a_to_b"
    for frame in scanned.get("frames") or []:
        envelope = frame.get("crypto_envelope")
        if not envelope:
            continue
        observed = frame.get("direction")
        applicable = observed == client_to_server
        envelope["applicability_resolved"] = True
        envelope["observed_direction"] = observed
        envelope["client_to_server_direction"] = client_to_server
        envelope["applicable_to_observed_direction"] = applicable
        if envelope.get("key_derivation"):
            envelope["key_derivation"]["applicable_to_observed_direction"] = applicable
        if not applicable:
            envelope.setdefault("diagnostics", []).append({
                "kind": "search_inbound_crypto_contract_direction_mismatch",
                "observed_direction": observed,
                "required_direction": client_to_server,
                "certainty": "verified_endpoint_role_mismatch",
            })
            continue

        raw_hex = frame.get("raw_hex") or ""
        raw = bytes.fromhex(raw_hex) if raw_hex else b""
        decryption = search_crypto_envelope.decrypt_inbound_frame(raw)
        frame["inbound_decryption"] = decryption
        frame["decryption_validated"] = bool(decryption.get("validated"))
        if decryption.get("validated"):
            frame["validated_packet_type"] = decryption.get("packet_type")
            frame["validated_packet_type_name"] = decryption.get("packet_type_name")
    return scanned
