"""Decode source-backed non-AH FFXI search-server responses after outbound crypto validation.

This module accepts only the validated result produced by
``search_crypto_envelope.decrypt_outbound_frame``. It never attempts to infer rolling state or to
pair requests/responses itself. Auction-house response types and unknown response layouts remain
opaque.
"""
from __future__ import annotations

import struct


SEARCH_TRAILER_SIZE = 0x14
SEARCH_LIST_DATA_START = 0x18

SEARCH_ENTITY_TYPE_NAMES = {
    0x00: "Name",
    0x01: "Area",
    0x02: "Nation",
    0x03: "Job",
    0x04: "Level",
    0x05: "Race",
    0x06: "Flags1",
    0x08: "Id",
    0x0D: "LinkshellRank",
    0x0E: "Unknown0E",
    0x10: "Rank",
    0x11: "Comment",
    0x16: "Flags2",
    0x17: "Language",
}


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _unpack_bits_be(data: bytes | bytearray, bit_offset: int, length: int) -> int:
    byte_offset = bit_offset >> 3
    inner_offset = bit_offset & 7
    actual_bytes = (inner_offset + length + 7) // 8
    value = int.from_bytes(data[byte_offset:byte_offset + actual_bytes], "little")
    mask = ((1 << length) - 1) << inner_offset
    return (value & mask) >> inner_offset


def _unpack_bits_le(data: bytes, bit_offset: int, length: int) -> int:
    """Independent equivalent of LandSandBoat common::unpackBitsLE()."""
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
        raise ValueError("packed response read exceeds available bytes")
    modified = bytearray(bytes_needed)
    for cur_byte, value in enumerate(raw):
        modified[bytes_needed - 1 - cur_byte] = value

    if bytes_needed == 1:
        mask = 0xFF >> inner_offset
        return (modified[0] & mask) >> (8 - (length + inner_offset))
    new_bit_offset = bytes_needed * 8 - (inner_offset + length)
    return _unpack_bits_be(modified, new_bit_offset, length)


def _decode_entity(block: bytes, entity_index: int, absolute_offset: int) -> dict:
    entries: list[dict] = []
    diagnostics: list[dict] = []
    fields: dict = {}
    bit_offset = 0
    total_bits = len(block) * 8

    def read(width: int, field: str, entry: dict) -> int | None:
        nonlocal bit_offset
        if bit_offset + width > total_bits:
            diagnostics.append({
                "kind": "truncated_search_response_entity_field",
                "entity_index": entity_index,
                "entry_type": entry.get("type"),
                "entry_type_name": entry.get("type_name"),
                "field": field,
                "bit_offset": bit_offset,
                "required_bits": width,
                "entity_bits": total_bits,
            })
            bit_offset = total_bits
            return None
        value = _unpack_bits_le(block, bit_offset, width)
        bit_offset += width
        return value

    while bit_offset < total_bits:
        remaining = total_bits - bit_offset
        if remaining <= 7:
            # CSearchList/CPartyList/CLinkshellList byte-align each entity. Source-generated padding
            # is zero; retain non-zero trailing bits as a diagnostic instead of interpreting them.
            padding = _unpack_bits_le(block, bit_offset, remaining) if remaining else 0
            if padding:
                diagnostics.append({
                    "kind": "nonzero_search_response_entity_padding",
                    "entity_index": entity_index,
                    "bit_offset": bit_offset,
                    "width": remaining,
                    "value": padding,
                })
            break
        if bit_offset + 5 > total_bits:
            break

        start = bit_offset
        entry_type = read(5, "entry_type", {})
        if entry_type is None:
            break
        entry = {
            "entry_index": len(entries),
            "bit_offset_start": start,
            "type": entry_type,
            "type_name": SEARCH_ENTITY_TYPE_NAMES.get(entry_type, "UNKNOWN"),
            "known_entity_type": entry_type in SEARCH_ENTITY_TYPE_NAMES,
            "value": None,
        }

        truncated = False
        if entry_type == 0x00:  # Name
            name_len = read(4, "name_length", entry)
            if name_len is None:
                truncated = True
            else:
                chars: list[str] = []
                for char_index in range(name_len):
                    char = read(7, f"name_char[{char_index}]", entry)
                    if char is None:
                        truncated = True
                        break
                    chars.append(chr(char))
                entry["value"] = {"name": "".join(chars), "length": name_len}
                fields["name"] = "".join(chars)
        elif entry_type == 0x01:  # Area
            value = read(10, "area", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["area"] = value
        elif entry_type == 0x02:  # Nation
            value = read(2, "nation", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["nation"] = value
        elif entry_type == 0x03:  # Job contains main + sub job
            main_job = read(5, "main_job", entry)
            sub_job = read(5, "sub_job", entry) if main_job is not None else None
            truncated = main_job is None or sub_job is None
            if not truncated:
                entry["value"] = {"main": main_job, "sub": sub_job}
                fields["main_job"] = main_job
                fields["sub_job"] = sub_job
        elif entry_type == 0x04:  # Level contains main + sub level
            main_level = read(8, "main_level", entry)
            sub_level = read(8, "sub_level", entry) if main_level is not None else None
            truncated = main_level is None or sub_level is None
            if not truncated:
                entry["value"] = {"main": main_level, "sub": sub_level}
                fields["main_level"] = main_level
                fields["sub_level"] = sub_level
        elif entry_type == 0x05:  # Race
            value = read(4, "race", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["race"] = value
        elif entry_type == 0x10:  # Rank
            value = read(8, "rank", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["rank"] = value
        elif entry_type == 0x06:  # Flags1
            value = read(16, "flags1", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["flags1"] = value
        elif entry_type == 0x08:  # Id, 20 bits on the wire
            value = read(20, "character_id_20bit", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["character_id_20bit"] = value
        elif entry_type == 0x0D:  # LinkshellRank + three IDs
            ranks = []
            for index in range(3):
                value = read(8, f"linkshell_rank[{index}]", entry)
                if value is None:
                    truncated = True
                    break
                ranks.append(value)
            ids = []
            if not truncated:
                for index in range(3):
                    value = read(32, f"linkshell_id[{index}]", entry)
                    if value is None:
                        truncated = True
                        break
                    ids.append(value)
            if not truncated:
                entry["value"] = {"ranks": ranks, "ids": ids}
                fields["linkshell_ranks"] = ranks
                fields["linkshell_ids"] = ids
        elif entry_type == 0x0E:  # Current producer writes an explicit 32-bit unknown field
            value = read(32, "unknown_0e", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["unknown_0e"] = value
        elif entry_type == 0x11:  # Search comment type
            value = read(32, "comment_type", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["comment_type"] = value
        elif entry_type == 0x16:  # Flags2
            value = read(32, "flags2", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["flags2"] = value
        elif entry_type == 0x17:  # Languages
            value = read(16, "languages", entry)
            truncated = value is None
            if value is not None:
                entry["value"] = value
                fields["languages"] = value
        else:
            entry["status"] = "unknown_entity_entry_type"
            entry["raw_remainder_hex"] = block[bit_offset // 8:].hex().upper()
            diagnostics.append({
                "kind": "unknown_search_response_entity_entry_type",
                "entity_index": entity_index,
                "entry_type": entry_type,
                "bit_offset": start,
            })
            entry["bit_offset_end"] = bit_offset
            entries.append(entry)
            break

        entry["bit_offset_end"] = bit_offset
        entry["status"] = "truncated" if truncated else "decoded"
        entries.append(entry)
        if truncated:
            break

    return {
        "entity_index": entity_index,
        "absolute_offset": absolute_offset,
        "encoded_size": len(block),
        "fields": fields,
        "entries": entries,
        "diagnostics": diagnostics,
        "raw_hex": block.hex().upper(),
        "fully_decoded": not diagnostics,
    }


def _resolve_0x82_family(predecessor_request: dict | None, entities: list[dict]) -> tuple[str, str]:
    if predecessor_request and predecessor_request.get("validated") and predecessor_request.get("packet_type_name") == "GROUP_LIST":
        fields = predecessor_request.get("fields") or {}
        if fields.get("party_id") or fields.get("alliance_id"):
            return "party_list", "verified_from_exact_GROUP_LIST_predecessor_fields"
        if fields.get("linkshell_id_1") or fields.get("linkshell_id_2"):
            return "linkshell_list", "verified_from_exact_GROUP_LIST_predecessor_fields"

    if entities and all(entity.get("fully_decoded") for entity in entities):
        if any("linkshell_ranks" in (entity.get("fields") or {}) for entity in entities):
            return "linkshell_list", "structurally_inferred_from_LinkshellRank_entries"
    return "party_or_linkshell_list", "ambiguous_without_exact_predecessor_context"


def decode_validated_outbound(outbound_result: dict, predecessor_request: dict | None = None) -> dict:
    """Decode a cryptographically validated outbound search response fail-closed."""
    result = {
        "validated_crypto": False,
        "decoded": False,
        "response_type": None,
        "response_type_name": "UNKNOWN",
        "classification_certainty": "unknown_opaque",
        "fields": {},
        "entities": [],
        "diagnostics": [],
        "raw_decrypted_hex": None,
    }
    if not outbound_result or not outbound_result.get("validated"):
        result["diagnostics"].append({"kind": "search_response_requires_validated_outbound_crypto"})
        return result
    decrypted_hex = outbound_result.get("decrypted_hex")
    if not decrypted_hex:
        result["diagnostics"].append({"kind": "validated_outbound_missing_decrypted_bytes"})
        return result

    try:
        data = bytes.fromhex(decrypted_hex)
    except ValueError:
        result["diagnostics"].append({"kind": "invalid_decrypted_search_response_hex"})
        return result

    result["validated_crypto"] = True
    result["raw_decrypted_hex"] = decrypted_hex.upper()
    if len(data) < 0x18 + SEARCH_TRAILER_SIZE:
        result["diagnostics"].append({
            "kind": "truncated_search_response_header",
            "observed_length": len(data),
        })
        return result

    packet_type = data[0x0B]
    result["response_type"] = packet_type

    if packet_type == 0x88:  # SearchCommentPacket
        result["response_type_name"] = "search_comment"
        result["classification_certainty"] = "verified_from_source_packet_discriminator"
        if len(data) != 204:
            result["diagnostics"].append({
                "kind": "search_comment_response_size_mismatch",
                "expected_length": 204,
                "observed_length": len(data),
            })
            return result
        declared_comment_length = _u16(data, 0x1C)
        comment_region = data[0x1E:0x9A]
        comment_bytes = comment_region.split(b"\x00", 1)[0].rstrip(b" ")
        result["fields"] = {
            "player_id": _u32(data, 0x18),
            "declared_comment_length": declared_comment_length,
            "comment": comment_bytes.decode("latin-1", errors="replace"),
            "is_final": bool(data[0x0A] & 0x80),
        }
        result["field_evidence"] = {
            "player_id": {"offset": 0x18, "length": 4, "certainty": "verified_from_source"},
            "declared_comment_length": {"offset": 0x1C, "length": 2, "certainty": "verified_from_source"},
            "comment": {"offset": 0x1E, "region_end": 0x9A, "certainty": "verified_from_source"},
        }
        if declared_comment_length != 124:
            result["diagnostics"].append({
                "kind": "search_comment_declared_length_unexpected",
                "source_constant": 124,
                "observed": declared_comment_length,
            })
        result["decoded"] = True
        return result

    if packet_type not in {0x80, 0x82}:
        result["diagnostics"].append({
            "kind": "validated_search_response_type_not_supported",
            "response_type": packet_type,
        })
        return result

    data_size = _u16(data, 0x08)
    expected_data_size = len(data) - SEARCH_TRAILER_SIZE
    if data_size != expected_data_size or data_size < SEARCH_LIST_DATA_START:
        result["diagnostics"].append({
            "kind": "search_list_data_size_mismatch",
            "declared_data_size": data_size,
            "expected_data_size": expected_data_size,
            "minimum_data_size": SEARCH_LIST_DATA_START,
        })
        return result

    entities: list[dict] = []
    pos = SEARCH_LIST_DATA_START
    while pos < data_size:
        encoded_size = data[pos]
        entity_start = pos + 1
        entity_end = entity_start + encoded_size
        if entity_end > data_size:
            result["diagnostics"].append({
                "kind": "truncated_search_response_entity",
                "entity_index": len(entities),
                "size_offset": pos,
                "declared_entity_size": encoded_size,
                "data_end": data_size,
            })
            break
        entity = _decode_entity(data[entity_start:entity_end], len(entities), entity_start)
        entities.append(entity)
        pos = entity_end

    result["entities"] = entities
    result["fields"] = {
        "data_size": data_size,
        "is_final": bool(data[0x0A] & 0x80),
        "raw_final_flag": data[0x0A],
        "entity_count": len(entities),
    }

    if packet_type == 0x80:
        result["response_type_name"] = "search_list"
        result["classification_certainty"] = "verified_from_source_packet_discriminator"
        result["fields"]["total_results"] = _u16(data, 0x0E)
        result["field_evidence"] = {
            "total_results": {"offset": 0x0E, "length": 2, "certainty": "verified_from_source"},
            "entities": {"offset": SEARCH_LIST_DATA_START, "certainty": "verified_from_source"},
        }
    else:
        family, certainty = _resolve_0x82_family(predecessor_request, entities)
        result["response_type_name"] = family
        result["classification_certainty"] = certainty
        if family == "party_list":
            result["fields"]["total_results"] = data[0x0E]
            result["field_evidence"] = {
                "total_results": {"offset": 0x0E, "length": 1, "certainty": "verified_from_source_and_predecessor"},
                "entities": {"offset": SEARCH_LIST_DATA_START, "certainty": "verified_from_source"},
            }
        elif family == "linkshell_list":
            result["fields"]["total_results"] = _u16(data, 0x0E)
            result["field_evidence"] = {
                "total_results": {"offset": 0x0E, "length": 2, "certainty": "verified_from_source"},
                "entities": {"offset": SEARCH_LIST_DATA_START, "certainty": "verified_from_source"},
            }
        else:
            result["fields"]["total_results_u8"] = data[0x0E]
            result["fields"]["total_results_u16"] = _u16(data, 0x0E)
            result["field_evidence"] = {
                "total_results": {"offset": 0x0E, "length": "ambiguous_1_or_2", "certainty": "ambiguous_without_predecessor"},
                "entities": {"offset": SEARCH_LIST_DATA_START, "certainty": "verified_from_source"},
            }

    entity_diagnostics = [d for entity in entities for d in entity.get("diagnostics") or []]
    result["diagnostics"].extend(entity_diagnostics)
    result["decoded"] = pos == data_size and not any(
        d["kind"].startswith("truncated_") or d["kind"].startswith("unknown_")
        for d in result["diagnostics"]
    )
    return result
