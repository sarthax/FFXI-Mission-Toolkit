"""Lineage-aware decoders for packed Character Editor state.

Packed character BLOBs are persisted from native server structs, so their layouts are versioned
contracts rather than generic bitsets. Decode only exact, known DSP/Topaz/LSB layouts and keep
writes disabled until a separate transaction layer explicitly opts into a verified codec.
"""
from __future__ import annotations

from typing import Any


MISSION_AREAS = (
    "San d'Oria",
    "Bastok",
    "Windurst",
    "Rise of the Zilart",
    "Treasures of Aht Urhgan",
    "Wings of the Goddess",
    "Chains of Promathia",
    "Assault",
    "Campaign",
    "A Crystalline Prophecy",
    "A Moogle Kupo d'Etat",
    "A Shantotto Ascension",
    "Seekers of Adoulin",
    "Rhapsodies of Vana'diel",
    "Reserved / TVR",
)

MISSION_AREA_COUNT = 15
MISSION_RECORD_SIZES = {
    # DarkStar missionlog_t: uint16 current + bool complete[64]
    "dsp": 66,
    # Topaz/LSB: uint16 current + two uint16 status words + bool complete[64]
    "topaz": 70,
    "lsb": 70,
}
KEY_ITEM_TABLE_COUNTS = {
    # DSP/Topaz keyitems_t: 7 tables, each two 512-bit sets.
    "dsp": 7,
    "topaz": 7,
    # Current LSB (Dec 2025+): 8 tables.
    "lsb": 8,
}
KEY_ITEM_BITS_PER_TABLE = 512
KEY_ITEM_SET_BYTES = KEY_ITEM_BITS_PER_TABLE // 8
KEY_ITEM_TABLE_BYTES = KEY_ITEM_SET_BYTES * 2

# Raw chars BLOBs copied directly into native character-state members. These sizes come from the
# corresponding DSP/Topaz/LSB CCharEntity declarations and are intentionally lineage-specific.
BITSET_BLOB_SIZES: dict[str, dict[str, int]] = {
    "abilities": {"dsp": 47, "topaz": 47, "lsb": 49},
    "weaponskills": {"dsp": 8, "topaz": 8, "lsb": 8},
    "titles": {"dsp": 94, "topaz": 94, "lsb": 143},
    "visited_zones": {"dsp": 36, "topaz": 36, "lsb": 38},
}
BITSET_MEANINGFUL_BITS: dict[str, dict[str, int]] = {
    "abilities": {family: size * 8 for family, size in BITSET_BLOB_SIZES["abilities"].items()},
    # Legacy std::bitset<49> occupies one 64-bit word; current LSB uses xi::bitset<64>.
    "weaponskills": {"dsp": 49, "topaz": 49, "lsb": 64},
    "titles": {family: size * 8 for family, size in BITSET_BLOB_SIZES["titles"].items()},
    "visited_zones": {family: size * 8 for family, size in BITSET_BLOB_SIZES["visited_zones"].items()},
}


class PackedCodecError(ValueError):
    """Packed data does not match the selected server lineage contract."""


def _family(value: str) -> str:
    family = str(value or "unknown").strip().lower()
    if family not in {"dsp", "topaz", "lsb"}:
        raise PackedCodecError(f"Unsupported packed-state adapter family: {family}")
    return family


def _bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise PackedCodecError(f"Packed value is not bytes-like: {type(value).__name__}")


def _validate_size(blob: bytes, *, expected: int, label: str, family: str) -> None:
    if len(blob) != expected:
        raise PackedCodecError(
            f"{label} BLOB length {len(blob)} does not match {family} layout ({expected} bytes)"
        )


def _set_bits(data: bytes) -> list[int]:
    result: list[int] = []
    for byte_index, byte in enumerate(data):
        if not byte:
            continue
        for bit in range(8):
            if byte & (1 << bit):
                result.append(byte_index * 8 + bit)
    return result


def decode_missions(value: Any, adapter_family: str) -> dict[str, Any]:
    """Decode the raw ``chars.missions`` native missionlog_t array.

    Completion entries are one-byte C++ bool values in all three supported lineages. DSP has a
    66-byte mission record; Topaz and LSB have 70-byte records with two additional status words.
    """
    family = _family(adapter_family)
    blob = _bytes(value)
    record_size = MISSION_RECORD_SIZES[family]
    expected = record_size * MISSION_AREA_COUNT
    _validate_size(blob, expected=expected, label="missions", family=family)

    areas: list[dict[str, Any]] = []
    for area_id in range(MISSION_AREA_COUNT):
        start = area_id * record_size
        current = int.from_bytes(blob[start : start + 2], "little")
        cursor = start + 2
        status_upper = None
        status_lower = None
        if record_size == 70:
            status_upper = int.from_bytes(blob[cursor : cursor + 2], "little")
            status_lower = int.from_bytes(blob[cursor + 2 : cursor + 4], "little")
            cursor += 4
        complete_bytes = blob[cursor : cursor + 64]
        completed_ids = [index for index, flag in enumerate(complete_bytes) if flag != 0]
        areas.append(
            {
                "area_id": area_id,
                "name": MISSION_AREAS[area_id],
                "current": current,
                "status_upper": status_upper,
                "status_lower": status_lower,
                "completed_ids": completed_ids,
                "completed_count": len(completed_ids),
            }
        )

    return {
        "codec": "missions",
        "family": family,
        "layout": "dsp-missionlog-v1" if family == "dsp" else "topaz-lsb-missionlog-v2",
        "blob_bytes": len(blob),
        "record_size": record_size,
        "area_count": MISSION_AREA_COUNT,
        "areas": areas,
        "write_enabled": False,
    }


def decode_key_items(value: Any, adapter_family: str) -> dict[str, Any]:
    """Decode ``chars.keyitems`` into owned/seen key-item IDs.

    Each table stores a 512-bit owned set followed by a 512-bit seen set. Key item IDs map as
    ``table = id // 512`` and ``bit = id % 512``. Current LSB stores eight tables; DSP/Topaz
    store seven. LSB's xi::bitset explicitly persists least-significant-bit-first bytes. The
    legacy std::bitset blobs use the same x86/libstdc++ persisted ordering used by those servers.
    """
    family = _family(adapter_family)
    blob = _bytes(value)
    table_count = KEY_ITEM_TABLE_COUNTS[family]
    expected = table_count * KEY_ITEM_TABLE_BYTES
    _validate_size(blob, expected=expected, label="keyitems", family=family)

    owned_ids: list[int] = []
    seen_ids: list[int] = []
    tables: list[dict[str, Any]] = []
    for table_id in range(table_count):
        start = table_id * KEY_ITEM_TABLE_BYTES
        owned_raw = blob[start : start + KEY_ITEM_SET_BYTES]
        seen_raw = blob[start + KEY_ITEM_SET_BYTES : start + KEY_ITEM_TABLE_BYTES]
        owned_local = _set_bits(owned_raw)
        seen_local = _set_bits(seen_raw)
        owned_global = [table_id * KEY_ITEM_BITS_PER_TABLE + bit for bit in owned_local]
        seen_global = [table_id * KEY_ITEM_BITS_PER_TABLE + bit for bit in seen_local]
        owned_ids.extend(owned_global)
        seen_ids.extend(seen_global)
        tables.append(
            {
                "table_id": table_id,
                "id_start": table_id * KEY_ITEM_BITS_PER_TABLE,
                "id_end": (table_id + 1) * KEY_ITEM_BITS_PER_TABLE - 1,
                "owned_count": len(owned_local),
                "seen_count": len(seen_local),
                "owned_ids": owned_global,
                "seen_ids": seen_global,
            }
        )

    return {
        "codec": "key_items",
        "family": family,
        "layout": "lsb-keyitems-8x512" if family == "lsb" else "dsp-topaz-keyitems-7x512",
        "blob_bytes": len(blob),
        "table_count": table_count,
        "bits_per_table": KEY_ITEM_BITS_PER_TABLE,
        "owned_ids": owned_ids,
        "seen_ids": seen_ids,
        "owned_count": len(owned_ids),
        "seen_count": len(seen_ids),
        "tables": tables,
        "write_enabled": False,
    }


def decode_character_bitset(capability: str, value: Any, adapter_family: str) -> dict[str, Any]:
    """Decode a byte-backed character bitset using the exact lineage-specific stored size.

    ``abilities``, ``titles`` and ``visited_zones`` are native uint8 arrays addressed through the
    server's ``hasBit(id, array, sizeof(array))`` helpers. ``weaponskills`` is stored as an
    8-byte bitset in all supported lineages, but only 49 bits are meaningful on DSP/Topaz while
    current LSB defines 64 bits. Reserved high bits are surfaced separately instead of silently
    treating them as valid legacy weaponskill IDs.
    """
    capability = str(capability or "").strip()
    if capability not in BITSET_BLOB_SIZES:
        raise PackedCodecError(f"Unsupported character bitset capability: {capability}")
    family = _family(adapter_family)
    blob = _bytes(value)
    expected = BITSET_BLOB_SIZES[capability][family]
    meaningful_bits = BITSET_MEANINGFUL_BITS[capability][family]
    _validate_size(blob, expected=expected, label=capability, family=family)

    all_set = _set_bits(blob)
    set_ids = [bit for bit in all_set if bit < meaningful_bits]
    reserved_set_ids = [bit for bit in all_set if bit >= meaningful_bits]
    if capability == "weaponskills":
        layout = "lsb-learned-weaponskills-64" if family == "lsb" else "dsp-topaz-learned-weaponskills-49-in-64"
    else:
        layout = f"{family}-{capability}-{expected * 8}bit"

    return {
        "codec": capability,
        "family": family,
        "layout": layout,
        "blob_bytes": len(blob),
        "storage_bits": len(blob) * 8,
        "meaningful_bits": meaningful_bits,
        "set_ids": set_ids,
        "set_count": len(set_ids),
        "reserved_set_ids": reserved_set_ids,
        "reserved_set_count": len(reserved_set_ids),
        "write_enabled": False,
    }


def decode_packed_field(capability: str, value: Any, adapter_family: str) -> dict[str, Any] | None:
    """Decode a supported packed capability, or return ``None`` for codecs not implemented yet."""
    if capability == "missions":
        return decode_missions(value, adapter_family)
    if capability == "key_items":
        return decode_key_items(value, adapter_family)
    if capability in BITSET_BLOB_SIZES:
        return decode_character_bitset(capability, value, adapter_family)
    return None
