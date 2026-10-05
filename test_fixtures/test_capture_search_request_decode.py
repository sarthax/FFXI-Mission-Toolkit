#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import search_request_decode


def _pack_bits_be(target: bytearray, value: int, bit_offset: int, length: int) -> None:
    byte_offset = bit_offset >> 3
    inner_offset = bit_offset & 7
    actual_bytes = (inner_offset + length + 7) // 8
    data = int.from_bytes(target[byte_offset:byte_offset + actual_bytes], "little")
    mask = ((1 << length) - 1) << inner_offset
    data = (data & ~mask) | ((value << inner_offset) & mask)
    target[byte_offset:byte_offset + actual_bytes] = data.to_bytes(actual_bytes, "little")


def _pack_bits_le(target: bytearray, value: int, bit_offset: int, length: int) -> int:
    """Independent test writer matching LSB common::packBitsLE()."""
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
        raise ValueError("packed test field exceeds 64-bit source helper")

    actual_bytes = (span + 7) // 8
    modified = bytearray(bytes_needed)
    for cur_byte in range(actual_bytes):
        modified[bytes_needed - 1 - cur_byte] = target[byte_offset + cur_byte]
    new_bit_offset = bytes_needed * 8 - (inner_offset + length)
    _pack_bits_be(modified, value, new_bit_offset, length)
    for cur_byte in range(actual_bytes):
        target[byte_offset + cur_byte] = modified[bytes_needed - 1 - cur_byte]
    return bit_offset + length


def decrypted_request(packet_type: int, writer=None, length: int = 64) -> bytes:
    packet = bytearray(length)
    struct.pack_into("<H", packet, 0, length)
    packet[4:8] = b"IXFF"
    packet[0x0B] = packet_type
    packet[-4:] = bytes.fromhex("01020304")
    if writer:
        writer(packet)
    hash_offset = length - 0x14
    packet[hash_offset:length - 4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def packed_search_request(packet_type: int = 0x03) -> bytes:
    packed = bytearray(29)
    bit = 0

    def ordinary(entry_type: int, width: int, value: int, *, sort: int = 0, present: int = 1) -> None:
        nonlocal bit
        bit = _pack_bits_le(packed, entry_type, bit, 5)
        bit = _pack_bits_le(packed, sort, bit, 1)
        bit = _pack_bits_le(packed, present, bit, 1)
        if present and width:
            bit = _pack_bits_le(packed, value, bit, width)

    # Name: ordinary header + raw length + 7-bit characters.
    bit = _pack_bits_le(packed, 0x00, bit, 5)
    bit = _pack_bits_le(packed, 0, bit, 1)
    bit = _pack_bits_le(packed, 1, bit, 1)
    bit = _pack_bits_le(packed, 3, bit, 5)
    for char in b"Bob":
        bit = _pack_bits_le(packed, char, bit, 7)

    ordinary(0x01, 10, 230)       # Area
    ordinary(0x02, 2, 1)          # Nation
    ordinary(0x03, 5, 12)         # Job
    ordinary(0x04, 16, (50 << 8) | 75)  # sequential reads yield min=50, max=75
    ordinary(0x05, 4, 3)          # Race
    ordinary(0x06, 16, 0x1234)    # Flags1
    ordinary(0x10, 16, (2 << 8) | 10)   # sequential reads yield min=2, max=10

    # Comment and Flags2 do not carry sort/present bits in LSB.
    bit = _pack_bits_le(packed, 0x11, bit, 5)
    bit = _pack_bits_le(packed, 0xAABBCCDD, bit, 32)
    bit = _pack_bits_le(packed, 0x16, bit, 5)
    bit = _pack_bits_le(packed, 0x55667788, bit, 32)

    # Friend is a zero-width special entry. It also makes the following count/ID tail meaningful.
    bit = _pack_bits_le(packed, 0x0C, bit, 5)
    assert bit == 230

    data_end = 0x11 + len(packed) + 2 + 8
    length = data_end + 0x14
    packet = bytearray(length)
    struct.pack_into("<H", packet, 0, length)
    packet[4:8] = b"IXFF"
    packet[0x0B] = packet_type
    packet[0x10] = len(packed)
    packet[0x11:0x11 + len(packed)] = packed
    tail = 0x11 + len(packed)
    struct.pack_into("<HII", packet, tail, 2, 0x11111111, 0x22222222)
    packet[-4:] = bytes.fromhex("01020304")
    hash_offset = length - 0x14
    packet[hash_offset:length - 4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def main():
    def write_ids(packet: bytearray):
        struct.pack_into("<H", packet, 0x10, 3)
        struct.pack_into("<III", packet, 0x12, 0x10000001, 0x10000002, 0x10000003)

    id_list = search_request_decode.decode_validated_request(decrypted_request(0x01, write_ids))
    assert id_list["validated"] is True, id_list
    assert id_list["packet_type_name"] == "ID_LIST", id_list
    assert id_list["decoder_status"] == "validated_basic_request_fields_decoded", id_list
    assert id_list["fields"] == {
        "requested_count": 3,
        "decoded_count": 3,
        "character_ids": [0x10000001, 0x10000002, 0x10000003],
    }, id_list
    assert id_list["field_evidence"]["character_ids"]["source_cap"] == 20, id_list

    # LSB caps ID_LIST to 20 and also to the number of complete uint32 IDs before the trailer.
    def write_overcount(packet: bytearray):
        struct.pack_into("<H", packet, 0x10, 99)
        struct.pack_into("<II", packet, 0x12, 7, 8)

    overcount = search_request_decode.decode_validated_request(decrypted_request(0x01, write_overcount, 46))
    assert overcount["validated"] is True, overcount
    assert overcount["fields"]["requested_count"] == 99, overcount
    assert overcount["fields"]["decoded_count"] == 2, overcount
    assert overcount["fields"]["character_ids"] == [7, 8], overcount

    def write_group(packet: bytearray):
        struct.pack_into("<IIII", packet, 0x10, 11, 22, 33, 44)

    group = search_request_decode.decode_validated_request(decrypted_request(0x02, write_group))
    assert group["validated"] is True, group
    assert group["packet_type_name"] == "GROUP_LIST", group
    assert group["fields"] == {
        "party_id": 11,
        "alliance_id": 22,
        "linkshell_id_1": 33,
        "linkshell_id_2": 44,
    }, group

    def write_comment(packet: bytearray):
        struct.pack_into("<I", packet, 0x10, 0x01020304)

    comment = search_request_decode.decode_validated_request(decrypted_request(0x08, write_comment))
    assert comment["validated"] is True, comment
    assert comment["packet_type_name"] == "SEARCH_COMMENT", comment
    assert comment["fields"] == {"player_id": 0x01020304}, comment

    search = search_request_decode.decode_validated_request(packed_search_request(0x03))
    assert search["validated"] is True, search
    assert search["packet_type_name"] == "SEARCH", search
    assert search["decoder_status"] == "validated_search_filter_fields_decoded", search
    fields = search["fields"]
    assert fields["query_size_bytes"] == 29, fields
    assert fields["name"] == "Bob", fields
    assert fields["areas"] == [230], fields
    assert fields["nation"] == 1, fields
    assert fields["job"] == 12, fields
    assert (fields["min_level"], fields["max_level"]) == (50, 75), fields
    assert fields["race"] == 3, fields
    assert (fields["min_rank"], fields["max_rank"]) == (2, 10), fields
    # Flags2 is later than Flags1 and therefore becomes LSB's final sr.flags value.
    assert fields["flags"] == 0x55667788, fields
    assert fields["comment_type"] == 0xAABBCCDD, fields
    assert fields["friends_only"] is True, fields
    assert fields["friend_requested_count"] == 2, fields
    assert fields["friend_character_ids"] == [0x11111111, 0x22222222], fields
    assert search["entries"][0]["type_name"] == "Name", search
    assert search["entries"][-1]["type_name"] == "Friend", search
    assert search["field_evidence"]["packed_query"]["bit_order"] == "LandSandBoat unpackBitsLE", search

    search_all = search_request_decode.decode_validated_request(packed_search_request(0x00))
    assert search_all["validated"] is True, search_all
    assert search_all["packet_type_name"] == "SEARCH_ALL", search_all
    assert search_all["fields"]["name"] == "Bob", search_all

    # Current LSB defines Language but its _HandleSearchRequest default branch assigns it no value
    # semantics. Keep the enum identity and control bits, but do not guess a payload width/value.
    def write_known_unhandled(packet: bytearray):
        packet[0x10] = 2
        bits = bytearray(2)
        off = _pack_bits_le(bits, 0x17, 0, 5)
        off = _pack_bits_le(bits, 1, off, 1)
        _pack_bits_le(bits, 1, off, 1)
        packet[0x11:0x13] = bits

    known_unhandled = search_request_decode.decode_validated_request(decrypted_request(0x03, write_known_unhandled, 39))
    assert known_unhandled["validated"] is True, known_unhandled
    assert any(e["type_name"] == "Language" for e in known_unhandled["entries"]), known_unhandled
    assert any(d["kind"] == "known_enum_unhandled_by_lsb_parser" for d in known_unhandled["diagnostics"]), known_unhandled

    # A declared packed query that runs into the 20-byte trailer fails closed before reading bits.
    def write_truncated_filter(packet: bytearray):
        packet[0x10] = 30

    truncated = search_request_decode.decode_validated_request(decrypted_request(0x03, write_truncated_filter, 40))
    assert truncated["validated"] is True, truncated
    assert truncated["decoder_status"] == "validated_search_filter_partial_or_rejected", truncated
    assert truncated["fields"] == {}, truncated
    assert any(d["kind"] == "truncated_search_filter_block" for d in truncated["diagnostics"]), truncated

    # Known AH traffic remains deliberately opaque in this capture/protocol slice.
    ah = search_request_decode.decode_validated_request(decrypted_request(0x15))
    assert ah["validated"] is True, ah
    assert ah["packet_type_name"] == "AH_REQUEST", ah
    assert ah["fields"] == {}, ah
    assert ah["decoder_status"] == "validated_request_type_payload_not_decoded", ah
    assert any(d["kind"] == "validated_search_request_body_not_supported" for d in ah["diagnostics"]), ah

    corrupt = bytearray(decrypted_request(0x08, write_comment))
    corrupt[0x10] ^= 0xFF
    rejected = search_request_decode.decode_validated_request(bytes(corrupt))
    assert rejected["validated"] is False, rejected
    assert rejected["fields"] == {}, rejected
    assert rejected["decoder_status"] == "rejected_before_request_decode", rejected

    print("Validated packed/basic search request decode regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
