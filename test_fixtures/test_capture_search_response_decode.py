#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import ffxi_blowfish, search_crypto_envelope, search_request_decode, search_response_decode


def _pack_bits_be(target: bytearray, value: int, bit_offset: int, length: int) -> None:
    byte_offset = bit_offset >> 3
    inner_offset = bit_offset & 7
    actual_bytes = (inner_offset + length + 7) // 8
    data = int.from_bytes(target[byte_offset:byte_offset + actual_bytes], "little")
    mask = ((1 << length) - 1) << inner_offset
    data = (data & ~mask) | ((value << inner_offset) & mask)
    target[byte_offset:byte_offset + actual_bytes] = data.to_bytes(actual_bytes, "little")


def _pack_bits_le(target: bytearray, value: int, bit_offset: int, length: int) -> int:
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
        raise ValueError("test pack field exceeds 64-bit source helper")
    actual_bytes = (span + 7) // 8
    modified = bytearray(bytes_needed)
    for cur_byte in range(actual_bytes):
        modified[bytes_needed - 1 - cur_byte] = target[byte_offset + cur_byte]
    _pack_bits_be(modified, value, bytes_needed * 8 - (inner_offset + length), length)
    for cur_byte in range(actual_bytes):
        target[byte_offset + cur_byte] = modified[bytes_needed - 1 - cur_byte]
    return bit_offset + length


def _finalize_plain(packet: bytearray, seed: bytes) -> bytes:
    struct.pack_into("<H", packet, 0, len(packet))
    packet[4:8] = b"IXFF"
    packet[-4:] = seed
    hash_offset = len(packet) - search_crypto_envelope.SEARCH_TRAILER_SIZE
    packet[hash_offset:-4] = hashlib.md5(packet[8:hash_offset]).digest()
    return bytes(packet)


def _encrypt_inbound(decrypted: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    key = bytes.fromhex(envelope["key_derivation"]["derived_blowfish_key_hex"])
    wire = bytearray(decrypted)
    wire[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], key)
    return bytes(wire)


def _encrypt_outbound(decrypted: bytes, state: bytes) -> bytes:
    envelope = search_crypto_envelope.inspect_frame(decrypted)
    start = envelope["encrypted_region"]["offset_start"]
    end = envelope["encrypted_region"]["offset_end"]
    wire = bytearray(decrypted)
    wire[start:end] = ffxi_blowfish.encrypt_blocks(decrypted[start:end], hashlib.md5(state).digest())
    return bytes(wire)


def _inbound_group_request(*, party: int = 0, alliance: int = 0, ls1: int = 0, ls2: int = 0) -> tuple[bytes, bytes, dict]:
    packet = bytearray(64)
    packet[0x0B] = 0x02
    struct.pack_into("<IIII", packet, 0x10, party, alliance, ls1, ls2)
    decrypted = _finalize_plain(packet, bytes.fromhex("01020304"))
    wire = _encrypt_inbound(decrypted)
    decoded = search_request_decode.decode_validated_request(decrypted)
    assert decoded["validated"] is True, decoded
    return wire, decrypted, decoded


def _entity_block(*, linkshell: bool = False) -> bytes:
    buf = bytearray(96)
    bit = 0

    bit = _pack_bits_le(buf, 0x00, bit, 5)  # Name
    bit = _pack_bits_le(buf, 4, bit, 4)
    for char in b"Test":
        bit = _pack_bits_le(buf, char, bit, 7)

    bit = _pack_bits_le(buf, 0x01, bit, 5)  # Area
    bit = _pack_bits_le(buf, 230, bit, 10)
    bit = _pack_bits_le(buf, 0x02, bit, 5)  # Nation
    bit = _pack_bits_le(buf, 1, bit, 2)
    bit = _pack_bits_le(buf, 0x03, bit, 5)  # Main/sub job
    bit = _pack_bits_le(buf, 12, bit, 5)
    bit = _pack_bits_le(buf, 6, bit, 5)
    bit = _pack_bits_le(buf, 0x04, bit, 5)  # Main/sub level
    bit = _pack_bits_le(buf, 75, bit, 8)
    bit = _pack_bits_le(buf, 37, bit, 8)
    bit = _pack_bits_le(buf, 0x05, bit, 5)  # Race
    bit = _pack_bits_le(buf, 3, bit, 4)
    bit = _pack_bits_le(buf, 0x10, bit, 5)  # Rank
    bit = _pack_bits_le(buf, 10, bit, 8)
    bit = _pack_bits_le(buf, 0x06, bit, 5)  # Flags1
    bit = _pack_bits_le(buf, 0x1234, bit, 16)
    bit = _pack_bits_le(buf, 0x08, bit, 5)  # 20-bit character id
    bit = _pack_bits_le(buf, 0xABCDE, bit, 20)

    if linkshell:
        bit = _pack_bits_le(buf, 0x0D, bit, 5)
        for rank in (2, 1, 0):
            bit = _pack_bits_le(buf, rank, bit, 8)
        for linkshell_id in (0x11112222, 0x33334444, 0):
            bit = _pack_bits_le(buf, linkshell_id, bit, 32)

    bit = _pack_bits_le(buf, 0x0E, bit, 5)
    bit = _pack_bits_le(buf, 0, bit, 32)
    bit = _pack_bits_le(buf, 0x11, bit, 5)
    bit = _pack_bits_le(buf, 0x01020304, bit, 32)
    bit = _pack_bits_le(buf, 0x16, bit, 5)
    bit = _pack_bits_le(buf, 0x55667788, bit, 32)
    bit = _pack_bits_le(buf, 0x17, bit, 5)
    bit = _pack_bits_le(buf, 0x0003, bit, 16)

    size = (bit + 7) // 8
    return bytes(buf[:size])


def _list_response(packet_type: int, state: bytes, *, linkshell: bool = False, total: int = 1) -> bytes:
    entity = _entity_block(linkshell=linkshell)
    data_size = 0x18 + 1 + len(entity)
    packet = bytearray(data_size + search_crypto_envelope.SEARCH_TRAILER_SIZE)
    struct.pack_into("<H", packet, 0x08, data_size)
    packet[0x0A] = 0x80
    packet[0x0B] = packet_type
    struct.pack_into("<H", packet, 0x0E, total)
    packet[0x18] = len(entity)
    packet[0x19:0x19 + len(entity)] = entity
    return _finalize_plain(packet, state[16:20])


def _search_comment_response(state: bytes) -> bytes:
    packet = bytearray(204)
    packet[0x08] = 154
    packet[0x0A] = 0x80
    packet[0x0B] = 0x88
    packet[0x0E] = 1
    struct.pack_into("<I", packet, 0x18, 0x11223344)
    struct.pack_into("<H", packet, 0x1C, 124)
    comment = b"Looking for party"
    packet[0x1E:0x1E + len(comment)] = comment
    packet[0x1E + len(comment):0x1E + 123] = b" " * (123 - len(comment))
    packet[0x9A] = 0
    return _finalize_plain(packet, state[16:20])


def _validated_outbound(plain: bytes, state_evidence: dict) -> dict:
    state = bytes.fromhex(state_evidence["state_hex"])
    wire = _encrypt_outbound(plain, state)
    result = search_crypto_envelope.decrypt_outbound_frame(wire, state_evidence)
    assert result["validated"] is True, result
    return result


def main():
    inbound_wire, inbound_plain, group_party = _inbound_group_request(party=0x1001)
    state_evidence = search_crypto_envelope.derive_outbound_state(inbound_wire, inbound_plain)
    assert state_evidence["validated"] is True, state_evidence
    state = bytes.fromhex(state_evidence["state_hex"])

    search_plain = _list_response(0x80, state)
    search_result = search_response_decode.decode_validated_outbound(_validated_outbound(search_plain, state_evidence))
    assert search_result["decoded"] is True, search_result
    assert search_result["response_type_name"] == "search_list", search_result
    assert search_result["classification_certainty"] == "verified_from_source_packet_discriminator", search_result
    assert search_result["fields"]["total_results"] == 1, search_result
    assert search_result["entities"][0]["fields"]["name"] == "Test", search_result
    assert search_result["entities"][0]["fields"]["area"] == 230, search_result
    assert search_result["entities"][0]["fields"]["main_job"] == 12, search_result
    assert search_result["entities"][0]["fields"]["sub_job"] == 6, search_result
    assert search_result["entities"][0]["fields"]["main_level"] == 75, search_result
    assert search_result["entities"][0]["fields"]["sub_level"] == 37, search_result
    assert search_result["entities"][0]["fields"]["character_id_20bit"] == 0xABCDE, search_result
    assert search_result["entities"][0]["fields"]["languages"] == 3, search_result

    party_plain = _list_response(0x82, state)
    party_outbound = _validated_outbound(party_plain, state_evidence)
    ambiguous_party = search_response_decode.decode_validated_outbound(party_outbound)
    assert ambiguous_party["response_type_name"] == "party_or_linkshell_list", ambiguous_party
    party_result = search_response_decode.decode_validated_outbound(party_outbound, group_party)
    assert party_result["decoded"] is True, party_result
    assert party_result["response_type_name"] == "party_list", party_result
    assert party_result["classification_certainty"] == "verified_from_exact_GROUP_LIST_predecessor_fields", party_result
    assert party_result["fields"]["total_results"] == 1, party_result

    ls_wire, ls_plain_req, group_ls = _inbound_group_request(ls1=0x11112222)
    ls_state_evidence = search_crypto_envelope.derive_outbound_state(ls_wire, ls_plain_req)
    assert ls_state_evidence["validated"] is True, ls_state_evidence
    ls_state = bytes.fromhex(ls_state_evidence["state_hex"])
    ls_plain = _list_response(0x82, ls_state, linkshell=True)
    ls_outbound = _validated_outbound(ls_plain, ls_state_evidence)
    ls_structural = search_response_decode.decode_validated_outbound(ls_outbound)
    assert ls_structural["response_type_name"] == "linkshell_list", ls_structural
    assert ls_structural["classification_certainty"] == "structurally_inferred_from_LinkshellRank_entries", ls_structural
    assert ls_structural["entities"][0]["fields"]["linkshell_ranks"] == [2, 1, 0], ls_structural
    assert ls_structural["entities"][0]["fields"]["linkshell_ids"] == [0x11112222, 0x33334444, 0], ls_structural
    ls_result = search_response_decode.decode_validated_outbound(ls_outbound, group_ls)
    assert ls_result["response_type_name"] == "linkshell_list", ls_result
    assert ls_result["classification_certainty"] == "verified_from_exact_GROUP_LIST_predecessor_fields", ls_result

    comment_plain = _search_comment_response(state)
    comment_result = search_response_decode.decode_validated_outbound(_validated_outbound(comment_plain, state_evidence))
    assert comment_result["decoded"] is True, comment_result
    assert comment_result["response_type_name"] == "search_comment", comment_result
    assert comment_result["fields"]["player_id"] == 0x11223344, comment_result
    assert comment_result["fields"]["declared_comment_length"] == 124, comment_result
    assert comment_result["fields"]["comment"] == "Looking for party", comment_result

    unknown_plain = bytearray(_list_response(0x80, state))
    unknown_plain[0x0B] = 0xFE
    unknown_plain = bytearray(_finalize_plain(unknown_plain, state[16:20]))
    unknown_result = search_response_decode.decode_validated_outbound(_validated_outbound(bytes(unknown_plain), state_evidence))
    assert unknown_result["validated_crypto"] is True, unknown_result
    assert unknown_result["decoded"] is False, unknown_result
    assert unknown_result["response_type_name"] == "UNKNOWN", unknown_result
    assert any(d["kind"] == "validated_search_response_type_not_supported" for d in unknown_result["diagnostics"]), unknown_result

    rejected = search_response_decode.decode_validated_outbound({"validated": False})
    assert rejected["validated_crypto"] is False, rejected
    assert any(d["kind"] == "search_response_requires_validated_outbound_crypto" for d in rejected["diagnostics"]), rejected

    print("Validated non-AH search response decode regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
