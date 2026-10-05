#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import search_request_decode


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

    print("Validated basic search request decode regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
