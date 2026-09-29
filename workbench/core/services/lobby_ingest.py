"""Validated FFXI retail lobby TCP framing and conservative field decoding.

Classification is structural. Ports are never sufficient. A message is accepted only when:
- the declared packet is fully present inside one reconstructed TCP byte range,
- the little-endian terminator bytes are exactly IXFF,
- the command is a known lobby command,
- packet_size is sane and command-size constraints match when fixed,
- the 16-byte MD5 identifier validates after zeroing bytes 12..27.

References: atom0s/XiPackets lobby documentation and matching LandSandBoat packet structs.
"""
from __future__ import annotations

import hashlib
import ipaddress
import struct


LOBBY_HEADER_SIZE = 28
LOBBY_TERMINATOR = b"IXFF"

COMMANDS = {
    0x0003: {"name": "ResponseOk", "direction": "s2c", "size": 0x20},
    0x0004: {"name": "ResponseError", "direction": "s2c", "size": 0x24},
    0x0005: {"name": "ResponseKey", "direction": "s2c", "size": 0x28},
    0x0007: {"name": "RequestSelectChr", "direction": "c2s", "size": 0x58},
    0x000B: {"name": "ResponseNextLogin", "direction": "s2c", "size": 0x48},
    0x0014: {"name": "RequestDeleteChr", "direction": "c2s", "size": 0x34},
    0x001F: {"name": "RequestGetChr", "direction": "c2s", "size": 0x2C},
    0x0020: {"name": "ResponseChrInfo2", "direction": "s2c", "size": None},
    0x0021: {"name": "RequestCreateChr", "direction": "c2s", "size": 0x90},
    0x0022: {"name": "RequestCreateChrPre", "direction": "c2s", "size": 0x60},
    0x0023: {"name": "ResponseWorldList", "direction": "s2c", "size": None},
    0x0024: {"name": "RequestQueryWorldList", "direction": "c2s", "size": 0x2C},
    0x0026: {"name": "RequestLobbyLogin", "direction": "c2s", "size": 0x98},
    0x0028: {"name": "RequestRenameChr", "direction": "c2s", "size": 0x44},
    0x002B: {"name": "RequestMoveGMChr", "direction": "c2s", "size": None},
}


def _cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", "replace").strip()


def _md5_valid(packet: bytes) -> bool:
    if len(packet) < LOBBY_HEADER_SIZE:
        return False
    expected = packet[12:28]
    work = bytearray(packet)
    work[12:28] = b"\x00" * 16
    return hashlib.md5(work).digest() == expected


def _ipv4_from_little_u32(raw4: bytes) -> str:
    """Lobby structs store a uint32 address; recover network-order dotted notation."""
    value = struct.unpack("<I", raw4)[0]
    return str(ipaddress.IPv4Address(value))


def _fixed_size_valid(command: int, packet_size: int) -> bool:
    spec = COMMANDS.get(command)
    if not spec:
        return False
    fixed = spec.get("size")
    return fixed is None or int(fixed) == packet_size


def _variable_layout_valid(command: int, packet: bytes) -> bool:
    size = len(packet)
    if command == 0x0020:  # ResponseChrInfo2
        if size < 0x20:
            return False
        count = struct.unpack_from("<I", packet, 28)[0]
        # XiPackets examples establish 0x8C bytes per character slot.
        return count <= 16 and size == 0x20 + count * 0x8C
    if command == 0x0023:  # ResponseWorldList
        if size < 0x20:
            return False
        count = struct.unpack_from("<I", packet, 28)[0]
        return count <= 256 and size == 0x20 + count * 20
    # Unknown fixed layout for RequestMoveGMChr: MD5+known command still required.
    return command == 0x002B


def validate_packet(packet: bytes) -> dict:
    if len(packet) < LOBBY_HEADER_SIZE:
        return {"valid": False, "reason": "too_short"}
    packet_size, terminator, command = struct.unpack_from("<III", packet, 0)
    if packet_size != len(packet):
        return {"valid": False, "reason": "size_mismatch", "packet_size": packet_size}
    if packet[4:8] != LOBBY_TERMINATOR:
        return {"valid": False, "reason": "terminator_mismatch", "command": command}
    if command not in COMMANDS:
        return {"valid": False, "reason": "unknown_command", "command": command}
    if packet_size < LOBBY_HEADER_SIZE or packet_size > 0x10000:
        return {"valid": False, "reason": "implausible_size", "packet_size": packet_size}
    if not _fixed_size_valid(command, packet_size):
        return {"valid": False, "reason": "fixed_size_mismatch", "command": command}
    if COMMANDS[command].get("size") is None and not _variable_layout_valid(command, packet):
        return {"valid": False, "reason": "variable_layout_mismatch", "command": command}
    if not _md5_valid(packet):
        return {"valid": False, "reason": "md5_mismatch", "command": command}
    return {
        "valid": True,
        "packet_size": packet_size,
        "command": command,
        "command_name": COMMANDS[command]["name"],
        "command_direction": COMMANDS[command]["direction"],
        "md5_valid": True,
    }


def decode_packet(packet: bytes) -> dict:
    validation = validate_packet(packet)
    if not validation.get("valid"):
        return {"validation": validation, "fields": {}}

    command = validation["command"]
    fields: dict = {}
    if command == 0x0003:
        fields["unknown0000"] = struct.unpack_from("<I", packet, 28)[0]
    elif command == 0x0004:
        fields["unknown0000"], fields["error_code"] = struct.unpack_from("<II", packet, 28)
    elif command == 0x0005:
        key, excode_server, excode_server2 = struct.unpack_from("<III", packet, 28)
        fields.update({
            "md5_key": key,
            "excode_server": excode_server,
            "excode_server2": excode_server2,
            "features": {
                "security_token": bool(excode_server2 & (1 << 0)),
                "wardrobe3": bool(excode_server2 & (1 << 2)),
                "wardrobe4": bool(excode_server2 & (1 << 3)),
                "wardrobe5": bool(excode_server2 & (1 << 4)),
                "wardrobe6": bool(excode_server2 & (1 << 5)),
                "wardrobe7": bool(excode_server2 & (1 << 6)),
                "wardrobe8": bool(excode_server2 & (1 << 7)),
            },
        })
    elif command == 0x0007:
        fields.update({
            "ffxi_id": struct.unpack_from("<I", packet, 28)[0],
            "ffxi_id_world": struct.unpack_from("<I", packet, 32)[0],
            "character_name": _cstr(packet[36:52]),
            "unknown0000": struct.unpack_from("<I", packet, 68)[0],
        })
    elif command == 0x000B:
        fields.update({
            "ffxi_id": struct.unpack_from("<I", packet, 28)[0],
            "ffxi_id_world": struct.unpack_from("<I", packet, 32)[0],
            "character_name": _cstr(packet[36:52]),
            "server_id": struct.unpack_from("<I", packet, 52)[0],
            "server_ip": _ipv4_from_little_u32(packet[56:60]),
            "server_port": struct.unpack_from("<I", packet, 60)[0],
            "cache_ip": _ipv4_from_little_u32(packet[64:68]),
            "cache_port": struct.unpack_from("<I", packet, 68)[0],
        })
    elif command == 0x0014:
        fields.update({
            "ffxi_id": struct.unpack_from("<I", packet, 28)[0],
            "ffxi_id_world": struct.unpack_from("<I", packet, 32)[0],
        })
    elif command == 0x0020:
        count = struct.unpack_from("<I", packet, 28)[0]
        fields["character_count"] = count
        entries = []
        pos = 32
        for _ in range(count):
            entry = packet[pos:pos + 0x8C]
            entries.append({
                "ffxi_id": struct.unpack_from("<I", entry, 0)[0],
                "ffxi_id_world": struct.unpack_from("<H", entry, 4)[0],
                "world_id": struct.unpack_from("<H", entry, 6)[0],
                "status": struct.unpack_from("<H", entry, 8)[0],
                "rename_required": bool(entry[10] & 0x01),
                "race_change": bool(entry[10] & 0x02),
                "ffxi_id_world_tbl": entry[11],
                "character_name": _cstr(entry[12:28]),
                "world_name": _cstr(entry[28:44]),
            })
            pos += 0x8C
        fields["characters"] = entries
    elif command == 0x0022:
        fields.update({
            "ffxi_id": struct.unpack_from("<I", packet, 28)[0],
            "character_name": _cstr(packet[32:48]),
            "world_name": _cstr(packet[64:80]),
        })
    elif command == 0x0023:
        count = struct.unpack_from("<I", packet, 28)[0]
        fields["world_count"] = count
        worlds = []
        pos = 32
        for _ in range(count):
            worlds.append({
                "world_id": struct.unpack_from("<I", packet, pos)[0],
                "world_name": _cstr(packet[pos + 4:pos + 20]),
            })
            pos += 20
        fields["worlds"] = worlds
    elif command == 0x0026:
        fields.update({
            "version_code": _cstr(packet[116:132]),
            "excode_client": struct.unpack_from("<I", packet, 132)[0],
        })
    elif command == 0x0028:
        fields.update({
            "ffxi_id": struct.unpack_from("<I", packet, 28)[0],
            "ffxi_id_world": struct.unpack_from("<I", packet, 32)[0],
            "new_name": _cstr(packet[36:52]),
        })

    return {"validation": validation, "fields": fields}


def scan_range(payload: bytes, seq_start: int) -> list[dict]:
    """Recover complete validated lobby packets from an observed contiguous TCP range."""
    messages = []
    pos = 0
    while pos + LOBBY_HEADER_SIZE <= len(payload):
        # Fast structural prefilter before MD5 work.
        if payload[pos + 4:pos + 8] != LOBBY_TERMINATOR:
            pos += 1
            continue
        declared = struct.unpack_from("<I", payload, pos)[0]
        command = struct.unpack_from("<I", payload, pos + 8)[0]
        if command not in COMMANDS or declared < LOBBY_HEADER_SIZE or declared > 0x10000:
            pos += 1
            continue
        end = pos + declared
        if end > len(payload):
            # Candidate begins here but is incomplete within this observed range.
            pos += 1
            continue
        packet = payload[pos:end]
        decoded = decode_packet(packet)
        if decoded["validation"].get("valid"):
            messages.append({
                "range_offset": pos,
                "seq_start": seq_start + pos,
                "seq_end": seq_start + end,
                "raw_hex": packet.hex().upper(),
                **decoded,
            })
            pos = end
        else:
            pos += 1
    return messages


def classify_flow(directions: dict[str, dict]) -> dict:
    """Classify a reconstructed flow from complete MD5-valid lobby messages only."""
    messages = []
    for direction in ("a_to_b", "b_to_a"):
        for range_index, rr in enumerate(directions.get(direction, {}).get("ranges", [])):
            payload = bytes.fromhex(rr["payload_hex"])
            for message_index, message in enumerate(scan_range(payload, int(rr["seq_start"]))):
                messages.append({
                    "direction": direction,
                    "range_index": range_index,
                    "message_index": message_index,
                    **message,
                })

    if not messages:
        return {
            "protocol_family": "unknown_tcp",
            "classification_validated": False,
            "messages": [],
            "endpoint_roles": None,
            "role_status": "unresolved",
        }

    role_votes = {}
    conflict = False
    for m in messages:
        expected = m["validation"]["command_direction"]
        direction = m["direction"]
        implied = (
            {"client": "a", "server": "b"}
            if (direction == "a_to_b" and expected == "c2s") or
               (direction == "b_to_a" and expected == "s2c")
            else {"client": "b", "server": "a"}
        )
        if role_votes and role_votes != implied:
            conflict = True
        role_votes = role_votes or implied

    return {
        "protocol_family": "ffxi_lobby",
        "classification_validated": True,
        "validation_basis": "complete_known_command+IXFF+declared_size+MD5",
        "messages": messages,
        "endpoint_roles": None if conflict else role_votes,
        "role_status": "conflicting" if conflict else "validated_from_command_direction",
    }
