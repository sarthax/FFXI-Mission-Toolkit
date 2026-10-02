"""Decode persisted Records of Eminence state for supported server lineages.

Topaz and current LandSandBoat persist ``eminencelog_t`` directly in ``chars.eminence``.
The native layout is 700 bytes because the 31 uint16 active IDs (62 bytes) are followed by
2 bytes of alignment padding before the 31 uint32 progress counters. Legacy DSP predates this
field and is intentionally unsupported rather than treated as an empty log.
"""
from __future__ import annotations

from typing import Any


EMINENCE_ACTIVE_SLOTS = 31
EMINENCE_ACTIVE_BYTES = EMINENCE_ACTIVE_SLOTS * 2
EMINENCE_PADDING_BYTES = 2
EMINENCE_PROGRESS_OFFSET = EMINENCE_ACTIVE_BYTES + EMINENCE_PADDING_BYTES
EMINENCE_PROGRESS_BYTES = EMINENCE_ACTIVE_SLOTS * 4
EMINENCE_COMPLETE_OFFSET = EMINENCE_PROGRESS_OFFSET + EMINENCE_PROGRESS_BYTES
EMINENCE_COMPLETE_BYTES = 512
EMINENCE_COMPLETE_BITS = EMINENCE_COMPLETE_BYTES * 8
EMINENCE_BLOB_BYTES = EMINENCE_COMPLETE_OFFSET + EMINENCE_COMPLETE_BYTES


class EminenceCodecError(ValueError):
    """Persisted Eminence data does not match a verified lineage contract."""


def _family(value: str) -> str:
    family = str(value or "unknown").strip().lower()
    if family == "dsp":
        raise EminenceCodecError("Legacy DSP has no verified chars.eminence persistence contract")
    if family not in {"topaz", "lsb"}:
        raise EminenceCodecError(f"Unsupported Eminence adapter family: {family}")
    return family


def _bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if value is None:
        return b""
    raise EminenceCodecError(f"Eminence value is not bytes-like: {type(value).__name__}")


def _set_bits(data: bytes) -> list[int]:
    out: list[int] = []
    for byte_index, byte in enumerate(data):
        if not byte:
            continue
        for bit in range(8):
            if byte & (1 << bit):
                out.append(byte_index * 8 + bit)
    return out


def decode_eminence(value: Any, adapter_family: str) -> dict[str, Any]:
    """Decode the native Topaz/LSB ``eminencelog_t`` BLOB without mutating it."""
    family = _family(adapter_family)
    blob = _bytes(value)
    if len(blob) != EMINENCE_BLOB_BYTES:
        raise EminenceCodecError(
            f"eminence BLOB length {len(blob)} does not match {family} layout ({EMINENCE_BLOB_BYTES} bytes)"
        )

    active: list[dict[str, Any]] = []
    for slot in range(EMINENCE_ACTIVE_SLOTS):
        active_offset = slot * 2
        progress_offset = EMINENCE_PROGRESS_OFFSET + slot * 4
        record_id = int.from_bytes(blob[active_offset : active_offset + 2], "little")
        progress = int.from_bytes(blob[progress_offset : progress_offset + 4], "little")
        active.append(
            {
                "slot": slot,
                "record_id": record_id,
                "progress": progress,
                "empty": record_id == 0,
                "time_limited": slot == EMINENCE_ACTIVE_SLOTS - 1,
            }
        )

    completed_ids = _set_bits(blob[EMINENCE_COMPLETE_OFFSET:])
    return {
        "codec": "eminence",
        "family": family,
        "layout": "topaz-lsb-eminencelog-native-v1",
        "blob_bytes": len(blob),
        "active_slot_count": EMINENCE_ACTIVE_SLOTS,
        "active_count": sum(1 for row in active if not row["empty"]),
        "active": active,
        "padding_offset": EMINENCE_ACTIVE_BYTES,
        "padding_bytes": EMINENCE_PADDING_BYTES,
        "padding_hex": blob[EMINENCE_ACTIVE_BYTES:EMINENCE_PROGRESS_OFFSET].hex(),
        "progress_offset": EMINENCE_PROGRESS_OFFSET,
        "complete_offset": EMINENCE_COMPLETE_OFFSET,
        "completion_bits": EMINENCE_COMPLETE_BITS,
        "completed_ids": completed_ids,
        "completed_count": len(completed_ids),
        "write_enabled": False,
    }
