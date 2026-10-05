#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct

from workbench.captures import map_framing


def map_login_datagram() -> bytes:
    inner = bytearray(map_framing.LOGIN_PACKET_SIZE)
    header = map_framing.LOGIN_OPCODE | ((map_framing.LOGIN_PACKET_SIZE // 4) << 9)
    struct.pack_into("<H", inner, 0, header)
    struct.pack_into("<H", inner, 2, 0x1234)  # observed sync bytes; semantics not used by classifier

    # Keep all semantic fields opaque, but populate deterministic bytes so the documented
    # LoginPacketCheck and transport MD5 exercise real data rather than an all-zero packet.
    for i in range(map_framing.LOGIN_PACKET_CHECK_SUM_START, map_framing.LOGIN_PACKET_SIZE):
        inner[i] = (i * 17 + 3) & 0xFF

    inner[map_framing.LOGIN_PACKET_CHECK_OFFSET] = (
        sum(inner[map_framing.LOGIN_PACKET_CHECK_SUM_START:map_framing.LOGIN_PACKET_SIZE]) & 0xFF
    )

    outer = bytearray(map_framing.FFXI_HEADER_SIZE)
    trailer = hashlib.md5(inner).digest()
    return bytes(outer + inner + trailer)


def main():
    packet = map_login_datagram()
    assert len(packet) == map_framing.MIN_DATAGRAM_SIZE, len(packet)

    decoded = map_framing.inspect_login_datagram(packet)
    assert decoded["recognized"] is True, decoded
    assert decoded["certainty"] == "verified", decoded
    assert decoded["message_type"] == "client_zone_login_0x000A", decoded
    assert decoded["field_evidence"]["opcode"]["value"] == 0x000A, decoded
    assert decoded["field_evidence"]["declared_inner_size"]["value"] == 0x005C, decoded
    assert decoded["field_evidence"]["outer_md5"]["valid"] is True, decoded
    assert decoded["field_evidence"]["LoginPacketCheck"]["valid"] is True, decoded
    assert decoded["opaque_inner_hex"], decoded

    bad_md5 = bytearray(packet)
    bad_md5[-1] ^= 0xFF
    rejected_md5 = map_framing.inspect_login_datagram(bytes(bad_md5))
    assert rejected_md5["recognized"] is False, rejected_md5
    assert any(d["kind"] == "map_outer_md5_mismatch" for d in rejected_md5["diagnostics"]), rejected_md5

    bad_sum = bytearray(packet)
    check_pos = map_framing.FFXI_HEADER_SIZE + map_framing.LOGIN_PACKET_CHECK_OFFSET
    bad_sum[check_pos] ^= 0x01
    inner_start = map_framing.FFXI_HEADER_SIZE
    inner_end = inner_start + map_framing.LOGIN_PACKET_SIZE
    bad_sum[inner_end:] = hashlib.md5(bad_sum[inner_start:inner_end]).digest()
    rejected_sum = map_framing.inspect_login_datagram(bytes(bad_sum))
    assert rejected_sum["recognized"] is False, rejected_sum
    assert any(d["kind"] == "map_login_packet_check_mismatch" for d in rejected_sum["diagnostics"]), rejected_sum

    wrong_opcode = bytearray(packet)
    header = 0x000B | ((map_framing.LOGIN_PACKET_SIZE // 4) << 9)
    struct.pack_into("<H", wrong_opcode, map_framing.FFXI_HEADER_SIZE, header)
    inner_start = map_framing.FFXI_HEADER_SIZE
    inner_end = inner_start + map_framing.LOGIN_PACKET_SIZE
    wrong_opcode[inner_end:] = hashlib.md5(wrong_opcode[inner_start:inner_end]).digest()
    rejected_opcode = map_framing.inspect_login_datagram(bytes(wrong_opcode))
    assert rejected_opcode["recognized"] is False, rejected_opcode
    assert any(d["kind"] == "map_non_login_datagram" for d in rejected_opcode["diagnostics"]), rejected_opcode

    truncated = map_framing.inspect_login_datagram(packet[:-1])
    assert truncated["recognized"] is False, truncated
    assert any(d["kind"] == "truncated_map_login_candidate" for d in truncated["diagnostics"]), truncated

    print("Map UDP 0x000A handshake regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
