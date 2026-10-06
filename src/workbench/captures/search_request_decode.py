"""Decode source-backed, already-decrypted FFXI search/cache requests.

Every entry point first requires the same framing and post-decrypt MD5 validation used by
LandSandBoat. Fixed-field requests and SEARCH/SEARCH_ALL's packed query grammar are decoded only
after that gate succeeds. Auction-house request/history bodies remain deliberately opaque.
"""
from __future__ import annotations

import struct

from workbench.captures import search_crypto_envelope


SEARCH_PACKET_TRAILER_SIZE = 0x14
SEARCH_QUERY_SIZE_OFFSET = 0x10
SEARCH_QUERY_DATA_OFFSET = 0x11
SEARCH_MAX_AREAS = 15
SEARCH_MAX_FRIEND_IDS = 200

SEARCH_TYPE_NAMES = {
    0x00: "Name",
    0x01: "Area",
    0x02: "Nation",
    0x03: "Job",
    0x04: "Level",
    0x05: "Race",
    0x06: "Flags1",
    0x08: "Id",
    0x0A: "Party",
    0x0B: "Linkshell",
    0x0C: "Friend",
    0x0D: "LinkshellRank",
    0x0E: "Unknown0E",
    0x10: "Rank",
    0x11: "Comment",
    0x13: "Linkshell2",
    0x16: "Flags2",
    0x17: "Language",
}

# These five entry kinds do not consume LSB's ordinary sortDescending/isPresent header bits.
_SEARCH_TYPES_WITHOUT_SORT_PRESENT = {0x0B, 0x0C, 0x11, 0x13, 0x16}


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _unpack_bits_be(data: bytes | bytearray, bit_offset: int, length: int) -> int:
    """Mirror the little-endian-host behavior of LSB's unpackBitsBE helper."""
    byte_offset = bit_offset >> 3
    bit_offset &= 7
    actual_bytes = (bit_offset + length + 7) // 8
    raw = data[byte_offset:byte_offset + actual_bytes]
    value = int.from_bytes(raw, "little")
    mask = ((1 << length) - 1) << bit_offset
    return (value & mask) >> bit_offset


def _unpack_bits_le(data: bytes, bit_offset: int, length: int) -> int:
    """Independent Python equivalent of LandSandBoat common::unpackBitsLE()."""
    byte_offset = bit_offset >> 3
    inner_offset = bit_offset & 7
    span = inner_offset + length
    if span <= 8:
        bytes_needed = 1
    elif span <= 16:
        bytes_needed = 2
    elif span <= 32:
        bytes_needed = 4
    elif span <= 64:
        bytes_needed = 8
    else:
        raise ValueError("unpackBitsLE span exceeds 64 bits")

    actual_bytes = (span + 7) // 8
    raw = data[byte_offset:byte_offset + actual_bytes]
    if len(raw) != actual_bytes:
        raise ValueError("packed bit read exceeds available bytes")

    modified = bytearray(bytes_needed)
    for cur_byte, value in enumerate(raw):
        modified[bytes_needed - 1 - cur_byte] = value

    if bytes_needed == 1:
        mask = 0xFF >> inner_offset
        return (modified[0] & mask) >> (8 - (length + inner_offset))

    new_bit_offset = bytes_needed * 8 - (inner_offset + length)
    return _unpack_bits_be(modified, new_bit_offset, length)


def _decode_packed_search_query(decrypted: bytes, data_end: int) -> dict:
    """Mirror LSB _HandleSearchRequest while stopping safely at the declared packed block."""
    result = {
        "decoded": False,
        "fields": {},
        "field_evidence": {},
        "entries": [],
        "diagnostics": [],
    }
    if data_end <= SEARCH_QUERY_SIZE_OFFSET:
        result["diagnostics"].append({
            "kind": "truncated_search_filter_request",
            "required_data_end": SEARCH_QUERY_DATA_OFFSET,
            "observed_data_end": data_end,
        })
        return result

    size = decrypted[SEARCH_QUERY_SIZE_OFFSET]
    query_end = SEARCH_QUERY_DATA_OFFSET + size
    if query_end > data_end:
        result["diagnostics"].append({
            "kind": "truncated_search_filter_block",
            "declared_query_bytes": size,
            "query_offset": SEARCH_QUERY_DATA_OFFSET,
            "required_data_end": query_end,
            "observed_data_end": data_end,
        })
        return result

    packed = decrypted[SEARCH_QUERY_DATA_OFFSET:query_end]
    workload_bits = size * 8
    bit_offset = 0

    name = ""
    raw_name_length = 0
    areas: list[int] = []
    nation = 255
    job = 0
    min_level = 0
    max_level = 0
    race = 255
    min_rank = 0
    max_rank = 0
    flags = 0
    comment_type = 0
    linkshell_id = None
    friends_only = False

    def need(width: int, entry: dict, field: str) -> bool:
        nonlocal bit_offset
        if bit_offset + width <= workload_bits:
            return True
        result["diagnostics"].append({
            "kind": "truncated_search_filter_value",
            "entry_index": len(result["entries"]),
            "entry_type": entry.get("type"),
            "entry_type_name": entry.get("type_name"),
            "field": field,
            "bit_offset": bit_offset,
            "required_bits": width,
            "workload_bits": workload_bits,
        })
        bit_offset = workload_bits
        return False

    while bit_offset < workload_bits:
        # Mirror LSB's terminal padding guard exactly. It deliberately refuses to interpret the
        # final five-or-fewer bits as another entry header.
        if bit_offset + 5 >= workload_bits:
            bit_offset = workload_bits
            break

        entry_start = bit_offset
        entry_type = _unpack_bits_le(packed, bit_offset, 5)
        bit_offset += 5
        entry = {
            "entry_index": len(result["entries"]),
            "bit_offset_start": entry_start,
            "type": entry_type,
            "type_name": SEARCH_TYPE_NAMES.get(entry_type, "UNKNOWN"),
            "known_search_type": entry_type in SEARCH_TYPE_NAMES,
            "sort_descending": None,
            "is_present": None,
            "value": None,
        }

        if entry_type not in _SEARCH_TYPES_WITHOUT_SORT_PRESENT:
            # Mirror LSB's padding guard before the ordinary two control bits.
            if bit_offset + 3 >= workload_bits:
                entry["bit_offset_end"] = workload_bits
                entry["status"] = "terminal_padding"
                result["entries"].append(entry)
                bit_offset = workload_bits
                break
            entry["sort_descending"] = _unpack_bits_le(packed, bit_offset, 1)
            bit_offset += 1
            entry["is_present"] = _unpack_bits_le(packed, bit_offset, 1)
            bit_offset += 1

        present = entry.get("is_present") == 1
        truncated = False

        if entry_type == 0x00:  # Name
            if present:
                if not need(5, entry, "raw_name_length"):
                    truncated = True
                else:
                    raw_name_length = _unpack_bits_le(packed, bit_offset, 5)
                    bit_offset += 5
                    chars: list[str] = []
                    for char_index in range(raw_name_length):
                        if not need(7, entry, f"name_char[{char_index}]"):
                            truncated = True
                            break
                        code = _unpack_bits_le(packed, bit_offset, 7)
                        bit_offset += 7
                        if char_index < 15:
                            chars.append(chr(code))
                    name = "".join(chars)
                    entry["value"] = {
                        "name": name,
                        "raw_length": raw_name_length,
                        "stored_length": len(name),
                        "source_storage_cap": 15,
                    }
        elif entry_type == 0x01:  # Area
            if present:
                if not need(10, entry, "area"):
                    truncated = True
                else:
                    area = _unpack_bits_le(packed, bit_offset, 10)
                    bit_offset += 10
                    stored = len(areas) < SEARCH_MAX_AREAS
                    if stored:
                        areas.append(area)
                    entry["value"] = {"area": area, "stored": stored, "source_storage_cap": SEARCH_MAX_AREAS}
        elif entry_type == 0x02:  # Nation
            if present:
                if not need(2, entry, "nation"):
                    truncated = True
                else:
                    nation = _unpack_bits_le(packed, bit_offset, 2)
                    bit_offset += 2
                    entry["value"] = nation
        elif entry_type == 0x03:  # Job
            if present:
                if not need(5, entry, "job"):
                    truncated = True
                else:
                    job = _unpack_bits_le(packed, bit_offset, 5)
                    bit_offset += 5
                    entry["value"] = job
        elif entry_type == 0x04:  # Level
            if present:
                if not need(16, entry, "level_range"):
                    truncated = True
                else:
                    min_level = _unpack_bits_le(packed, bit_offset, 8)
                    bit_offset += 8
                    max_level = _unpack_bits_le(packed, bit_offset, 8)
                    bit_offset += 8
                    entry["value"] = {"min": min_level, "max": max_level}
        elif entry_type == 0x05:  # Race
            if present:
                if not need(4, entry, "race"):
                    truncated = True
                else:
                    race = _unpack_bits_le(packed, bit_offset, 4)
                    bit_offset += 4
                    entry["value"] = race
        elif entry_type == 0x06:  # Flags1
            if present:
                if not need(16, entry, "flags1"):
                    truncated = True
                else:
                    flags = _unpack_bits_le(packed, bit_offset, 16)
                    bit_offset += 16
                    entry["value"] = flags
        elif entry_type == 0x10:  # Rank
            if present:
                if not need(16, entry, "rank_range"):
                    truncated = True
                else:
                    min_rank = _unpack_bits_le(packed, bit_offset, 8)
                    bit_offset += 8
                    max_rank = _unpack_bits_le(packed, bit_offset, 8)
                    bit_offset += 8
                    entry["value"] = {"min": min_rank, "max": max_rank}
        elif entry_type == 0x11:  # Comment
            if not need(32, entry, "comment_type"):
                truncated = True
            else:
                comment_type = _unpack_bits_le(packed, bit_offset, 32)
                bit_offset += 32
                entry["value"] = comment_type
        elif entry_type in {0x0B, 0x13}:  # Linkshell / Linkshell2
            if not need(32, entry, "linkshell_id"):
                truncated = True
            else:
                linkshell_id = _unpack_bits_le(packed, bit_offset, 32)
                bit_offset += 32
                entry["value"] = linkshell_id
        elif entry_type == 0x0C:  # Friend
            friends_only = True
            entry["value"] = True
        elif entry_type == 0x16:  # Flags2
            if not need(32, entry, "flags2"):
                truncated = True
            else:
                flags = _unpack_bits_le(packed, bit_offset, 32)
                bit_offset += 32
                entry["value"] = flags
        else:
            # Current LSB defines several additional enum values but its parser's default branch
            # assigns no payload semantics to them. Preserve exactly that distinction.
            entry["status"] = "known_enum_unhandled_by_lsb_parser" if entry_type in SEARCH_TYPE_NAMES else "unknown_entry_type"
            result["diagnostics"].append({
                "kind": entry["status"],
                "entry_type": entry_type,
                "entry_type_name": entry["type_name"],
                "bit_offset": entry_start,
            })

        entry["bit_offset_end"] = bit_offset
        entry.setdefault("status", "truncated" if truncated else "decoded")
        result["entries"].append(entry)
        if truncated:
            break

    friend_character_ids: list[int] = []
    friend_requested_count = None
    if friends_only:
        count_offset = query_end
        ids_offset = count_offset + 2
        if data_end >= ids_offset:
            friend_requested_count = _u16(decrypted, count_offset)
            available_count = max(0, (data_end - ids_offset) // 4)
            decoded_count = min(friend_requested_count, SEARCH_MAX_FRIEND_IDS, available_count)
            friend_character_ids = [_u32(decrypted, ids_offset + index * 4) for index in range(decoded_count)]
        else:
            result["diagnostics"].append({
                "kind": "truncated_friend_id_list",
                "count_offset": count_offset,
                "required_data_end": ids_offset,
                "observed_data_end": data_end,
            })

    result["decoded"] = not any(d["kind"].startswith("truncated_") for d in result["diagnostics"])
    result["fields"] = {
        "query_size_bytes": size,
        "bits_consumed": bit_offset,
        "workload_bits": workload_bits,
        "remaining_bits": max(0, workload_bits - bit_offset),
        "name": name,
        "raw_name_length": raw_name_length,
        "areas": areas,
        "nation": nation,
        "job": job,
        "min_level": min_level,
        "max_level": max_level,
        "race": race,
        "min_rank": min_rank,
        "max_rank": max_rank,
        "flags": flags,
        "comment_type": comment_type,
        "linkshell_id": linkshell_id,
        "friends_only": friends_only,
        "friend_requested_count": friend_requested_count,
        "friend_character_ids": friend_character_ids,
    }
    result["field_evidence"] = {
        "query_size_bytes": {"offset": SEARCH_QUERY_SIZE_OFFSET, "length": 1, "certainty": "verified_from_source"},
        "packed_query": {
            "offset": SEARCH_QUERY_DATA_OFFSET,
            "length": size,
            "raw_hex": packed.hex().upper(),
            "bit_order": "LandSandBoat unpackBitsLE",
            "certainty": "verified_from_source",
        },
        "entries": {
            "count": len(result["entries"]),
            "certainty": "verified_from_source_with_safe_bounds",
            "source": "LandSandBoat SearchHandler::_HandleSearchRequest",
        },
        "friend_character_ids": {
            "count_offset": query_end if friends_only else None,
            "ids_offset": query_end + 2 if friends_only else None,
            "source_cap": SEARCH_MAX_FRIEND_IDS,
            "certainty": "verified_from_source" if friends_only else "not_applicable",
        },
    }
    return result


def decode_validated_request(decrypted: bytes) -> dict:
    """Validate then decode request fields directly consumed by current LSB handlers."""
    validation = search_crypto_envelope.validate_decrypted_frame(decrypted)
    result = {
        "validated": validation["validated"],
        "packet_type": validation.get("packet_type"),
        "packet_type_name": validation.get("packet_type_name"),
        "validation": validation,
        "fields": {},
        "field_evidence": {},
        "decoder_status": "rejected_before_request_decode",
        "diagnostics": list(validation.get("diagnostics") or []),
        "raw_hex": decrypted.hex().upper(),
    }
    if not validation["validated"]:
        return result

    packet_type = validation["packet_type"]
    data_end = len(decrypted) - SEARCH_PACKET_TRAILER_SIZE
    result["decoder_status"] = "validated_request_type_payload_not_decoded"

    if packet_type in {0x00, 0x03}:  # SEARCH_ALL / SEARCH
        decoded = _decode_packed_search_query(decrypted, data_end)
        result["fields"] = decoded["fields"]
        result["field_evidence"] = decoded["field_evidence"]
        result["entries"] = decoded["entries"]
        result["diagnostics"].extend(decoded["diagnostics"])
        result["decoder_status"] = (
            "validated_search_filter_fields_decoded" if decoded["decoded"]
            else "validated_search_filter_partial_or_rejected"
        )
        return result

    if packet_type == 0x01:  # ID_LIST
        count_offset = 0x10
        ids_offset = 0x12
        if data_end < ids_offset:
            result["diagnostics"].append({
                "kind": "truncated_id_list_request",
                "required_data_end": ids_offset,
                "observed_data_end": data_end,
            })
            return result
        requested_count = _u16(decrypted, count_offset)
        available_count = max(0, (data_end - ids_offset) // 4)
        decoded_count = min(requested_count, 20, available_count)
        character_ids = [_u32(decrypted, ids_offset + 4 * i) for i in range(decoded_count)]
        result["fields"] = {
            "requested_count": requested_count,
            "decoded_count": decoded_count,
            "character_ids": character_ids,
        }
        result["field_evidence"] = {
            "requested_count": {"offset": count_offset, "length": 2, "certainty": "verified_from_source"},
            "character_ids": {
                "offset": ids_offset,
                "element_length": 4,
                "decoded_count": decoded_count,
                "source_cap": 20,
                "certainty": "verified_from_source",
            },
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    if packet_type == 0x02:  # GROUP_LIST
        required_end = 0x20
        if data_end < required_end:
            result["diagnostics"].append({
                "kind": "truncated_group_list_request",
                "required_data_end": required_end,
                "observed_data_end": data_end,
            })
            return result
        result["fields"] = {
            "party_id": _u32(decrypted, 0x10),
            "alliance_id": _u32(decrypted, 0x14),
            "linkshell_id_1": _u32(decrypted, 0x18),
            "linkshell_id_2": _u32(decrypted, 0x1C),
        }
        result["field_evidence"] = {
            "party_id": {"offset": 0x10, "length": 4, "certainty": "verified_from_source"},
            "alliance_id": {"offset": 0x14, "length": 4, "certainty": "verified_from_source"},
            "linkshell_id_1": {"offset": 0x18, "length": 4, "certainty": "verified_from_source"},
            "linkshell_id_2": {"offset": 0x1C, "length": 4, "certainty": "verified_from_source"},
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    if packet_type == 0x08:  # SEARCH_COMMENT
        required_end = 0x14
        if data_end < required_end:
            result["diagnostics"].append({
                "kind": "truncated_search_comment_request",
                "required_data_end": required_end,
                "observed_data_end": data_end,
            })
            return result
        result["fields"] = {"player_id": _u32(decrypted, 0x10)}
        result["field_evidence"] = {
            "player_id": {"offset": 0x10, "length": 4, "certainty": "verified_from_source"},
        }
        result["decoder_status"] = "validated_basic_request_fields_decoded"
        return result

    # Auction-house request/history bodies and unknown validated request types stay opaque.
    result["diagnostics"].append({
        "kind": "validated_search_request_body_not_supported",
        "packet_type": packet_type,
        "packet_type_name": validation.get("packet_type_name"),
    })
    return result
