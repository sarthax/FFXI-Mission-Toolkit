"""Portable read-only native packet session parsing and canonical ingestion.

This is an offline adapter, not a packet hook or live transport. A complete
source is validated before any database mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from workbench.core.services import capture_integrity as integrity
from workbench.core.services import raw_packet_ingest
from .live_capture_contract import LiveCaptureSequence, LivePacketEnvelope

MAX_SESSION_BYTES = 16 * 1024 * 1024
MAX_ROWS = 10000


def parse_session(data: bytes):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SESSION_BYTES:
        raise ValueError("invalid native capture source size")
    if not data.endswith(b"\n"):
        raise ValueError("incomplete native capture session")
    sequence = LiveCaptureSequence()
    rows = []
    offset = 0
    for number, line in enumerate(data.splitlines(keepends=True), 1):
        if len(rows) >= MAX_ROWS or len(line) > 16384:
            raise ValueError("native capture row limit exceeded")
        try:
            mapping = json.loads(line.decode("utf-8"))
            packet = LivePacketEnvelope.from_mapping(mapping)
        except (UnicodeError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"invalid native packet row {number}") from exc
        sequence.accept(packet)
        rows.append((packet, number, offset, offset + len(line)))
        offset += len(line)
    return rows


def ingest_session(con, capture_id: int, src, relname: str) -> int:
    data = src.read_bytes(relname)
    rows = parse_session(data)
    digest = integrity.sha256_bytes(data)
    con.execute("SAVEPOINT native_live_capture")
    try:
        for packet, line, start, end in rows:
            ts = datetime.fromtimestamp(packet.observed_at_ns / 1_000_000_000, timezone.utc).isoformat()
            raw_packet_ingest.insert_raw_packet(
                con, capture_id, ts=ts, direction=packet.direction,
                opcode=packet.opcode, raw_hex=packet.raw_hex,
                packet_size=len(packet.raw_bytes),
                is_injected=packet.is_injected, is_blocked=packet.is_blocked,
                source_format="native_live_capture",
                source_native_id=f"{relname}:{packet.client_id}:{packet.session_id}:{packet.sequence}",
                filename=relname, source_sha256=digest, locator_basis="line",
                start_line=line, end_line=line, start_offset=start, end_offset=end,
                details={
                    "schema_version": packet.schema_version, "client_id": packet.client_id,
                    "session_id": packet.session_id, "source_sequence": packet.sequence,
                    "observed_at_ns": packet.observed_at_ns,
                    "dropped_before": packet.dropped_before,
                    "hook_stage": "addon_callback_original", "wire_verified": False,
                },
            )
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT native_live_capture")
        raise
    finally:
        con.execute("RELEASE SAVEPOINT native_live_capture")
    return len(rows)


def parse_segments(segments: list[bytes]):
    """Validate ordered rotated files as one logical recording.

    Every segment is newline-terminated. Packet order and source loss are
    checked across boundaries, not reset for each file.
    """
    if not segments:
        raise ValueError("empty native capture session")
    sequence = LiveCaptureSequence()
    parsed = []
    for segment_number, data in enumerate(segments, 1):
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SESSION_BYTES:
            raise ValueError("invalid native segment size")
        if not data.endswith(b"\n"):
            raise ValueError("truncated native segment")
        rows = []
        offset = 0
        for line_number, line in enumerate(data.splitlines(keepends=True), 1):
            if len(line) > 16384 or len(rows) >= MAX_ROWS:
                raise ValueError("native segment row limit exceeded")
            try:
                packet = LivePacketEnvelope.from_mapping(json.loads(line.decode("utf-8")))
                sequence.accept(packet)
            except (UnicodeError, ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"invalid native segment {segment_number} row {line_number}") from exc
            rows.append((packet, line_number, offset, offset + len(line)))
            offset += len(line)
        parsed.append(rows)
    return parsed


def ingest_segments(con, capture_id: int, src, relnames: list[str]) -> int:
    """Atomically import a complete ordered multi-segment recording."""
    if not relnames or len(set(relnames)) != len(relnames):
        raise ValueError("segment filenames must be unique")
    payloads = [src.read_bytes(name) for name in relnames]
    parsed = parse_segments(payloads)
    con.execute("SAVEPOINT native_live_segments")
    total = 0
    try:
        for name, data, rows in zip(relnames, payloads, parsed):
            digest = integrity.sha256_bytes(data)
            for packet, line, start, end in rows:
                ts = datetime.fromtimestamp(packet.observed_at_ns / 1_000_000_000, timezone.utc).isoformat()
                raw_packet_ingest.insert_raw_packet(
                    con, capture_id, ts=ts, direction=packet.direction,
                    opcode=packet.opcode, raw_hex=packet.raw_hex,
                    packet_size=len(packet.raw_bytes),
                    is_injected=packet.is_injected, is_blocked=packet.is_blocked,
                    source_format="native_live_capture",
                    source_native_id=f"{name}:{packet.client_id}:{packet.session_id}:{packet.sequence}",
                    filename=name, source_sha256=digest, locator_basis="line",
                    start_line=line, end_line=line, start_offset=start, end_offset=end,
                    details={
                        "schema_version": packet.schema_version,
                        "client_id": packet.client_id, "session_id": packet.session_id,
                        "source_sequence": packet.sequence, "observed_at_ns": packet.observed_at_ns,
                        "dropped_before": packet.dropped_before,
                        "hook_stage": "addon_callback_original", "wire_verified": False,
                    },
                )
                total += 1
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT native_live_segments")
        raise
    finally:
        con.execute("RELEASE SAVEPOINT native_live_segments")
    return total
