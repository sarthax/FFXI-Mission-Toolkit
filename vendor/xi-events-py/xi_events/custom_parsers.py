"""(size, args_dict) parsers for the 32 variable-length opcodes."""

from __future__ import annotations

import struct
from typing import Callable


def _read_u16(data: bytes, pos: int) -> int:
    return struct.unpack_from("<H", data, pos)[0]


def _read_u32(data: bytes, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def _from_table(
    data: bytes, pos: int, length_map: dict[int, int], default: int = 2
) -> tuple[int, dict]:
    """Size is purely a function of the mode byte at data[pos+1]."""
    if pos + 1 >= len(data):
        return min(default, len(data) - pos), {"mode": 0}
    mode = data[pos + 1]
    return length_map.get(mode, default), {"mode": mode}


def parse_move_entity(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    if mode == 0 and pos + 8 <= len(data):
        return 8, {
            "mode": mode,
            "x": _read_u16(data, pos + 2),
            "z": _read_u16(data, pos + 4),
            "y": _read_u16(data, pos + 6),
        }
    return (8, {"mode": mode}) if mode == 0 else (2, {"mode": mode})


def parse_update_entity_position(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    if mode == 1:
        return 2, {"mode": mode}
    if pos + 10 <= len(data):
        return 10, {
            "mode": mode,
            "x": _read_u16(data, pos + 2),
            "z": _read_u16(data, pos + 4),
            "y": _read_u16(data, pos + 6),
            "move_time": _read_u16(data, pos + 8),
        }
    return 10, {"mode": mode}


def parse_update_entity_data_multi(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    sizes = {0: 4, 1: 8, 2: 4, 3: 8, 4: 8, 5: 7, 6: 6, 7: 4, 8: 8}
    return sizes.get(mode, 4), {"mode": mode}


def parse_update_event_position(data: bytes, pos: int) -> tuple[int, dict]:
    """Mode 0: 8 bytes (x, z, y). Else: 2 bytes."""
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    if mode == 0 and pos + 8 <= len(data):
        return 8, {
            "mode": mode,
            "x": _read_u16(data, pos + 2),
            "z": _read_u16(data, pos + 4),
            "y": _read_u16(data, pos + 6),
        }
    return (8 if mode == 0 else 2), {"mode": mode}


def parse_load_event_weather(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0: 10, 1: 6}, default=4)


def parse_multi_handler_complex(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(
        data, pos, {0: 2, 1: 2, 2: 6, 3: 16, 4: 16, 5: 18, 6: 18, 7: 14}, default=2
    )


def parse_adjust_render_flags1_multi(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0: 4, 1: 4, 2: 6}, default=2)


def parse_handle_string_input(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 2, {"input_type": 0}
    t = data[pos + 1]
    sizes = {
        0x00: 2,
        0x01: 2,
        0x02: 2,
        0x21: 2,
        0x51: 2,
        0x53: 2,
        0x03: 4,
        0x10: 4,
        0x11: 4,
        0x13: 4,
        0x30: 4,
        0x31: 4,
        0x40: 4,
        0x50: 4,
        0x52: 4,
        0x55: 4,
        0x12: 6,
        0x32: 6,
        0x41: 8,
        0x54: 10,
        0x20: 16,
    }
    return sizes.get(t, 2), {"input_type": t}


def parse_load_room(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {1: 2}, default=4)


def parse_look_at_entity(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    size = 12 if mode == 1 else 10
    if pos + size > len(data):
        return min(size, len(data) - pos), {"mode": mode}
    out = {"mode": mode, "looker": _read_u32(data, pos + 2)}
    if size >= 10:
        out["target"] = _read_u32(data, pos + 6)
    if size >= 12:
        out["work"] = _read_u16(data, pos + 10)
    return size, out


def parse_vm_control(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0: 6, 1: 7, 2: 6, 3: 2, 4: 8, 5: 6}, default=2)


def parse_chocobo_mount_handler(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(
        data, pos, {0: 6, 1: 6, 2: 6, 3: 16, 4: 6, 5: 6, 6: 18, 7: 8, 8: 6}, default=6
    )


def parse_world_pass_handler_a(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0x02: 2}, default=1)


def parse_world_pass_handler_b(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0x02: 2}, default=1)


_OP9D_SIZES = {
    0x00: 8,
    0x01: 8,
    0x02: 6,
    0x03: 8,
    0x04: 8,
    0x05: 8,
    0x06: 8,
    0x07: 6,
    0x08: 23,
    0x09: 9,
    0x0A: 10,
    0x0B: 10,
    0x0C: 8,
    0x0D: 10,
    0x0E: 10,
    0x0F: 10,
    0x10: 10,
}


def parse_string_handler_multi(data: bytes, pos: int) -> tuple[int, dict]:
    """0x9D — 17-case dispatcher. Each mode has a fixed-size operand block.
    Most modes carry a tuple of u16 operands; 0x08 carries a 16-byte ASCII
    name buffer and 0x09 mixes a u32 + u16 + u8.

    Returns ``{mode, words}`` where ``words`` is a tuple of integers (or for
    mode 0x08, a tuple ending in the decoded name string).
    """
    if pos + 1 > len(data):
        return 1, {"mode": 0, "words": ()}
    mode = data[pos + 1]
    size = _OP9D_SIZES.get(mode, 2)
    if pos + size > len(data):
        return min(size, len(data) - pos), {"mode": mode, "words": ()}
    body = data[pos + 2 : pos + size]

    if mode == 0x08 and len(body) == 21:
        # u8, u16, 16-byte name, u16.
        name = body[3:19].split(b"\x00", 1)[0].decode("ascii", errors="replace")
        words = (
            body[0],
            int.from_bytes(body[1:3], "little"),
            name,
            int.from_bytes(body[19:21], "little"),
        )
    elif mode == 0x09 and len(body) == 7:
        words = (
            int.from_bytes(body[0:4], "little"),  # u32
            int.from_bytes(body[4:6], "little"),  # u16
            body[6],  # u8
        )
    elif len(body) % 2 == 0 and len(body) > 0:
        words = tuple(
            int.from_bytes(body[i : i + 2], "little") for i in range(0, len(body), 2)
        )
    else:
        words = tuple(body)
    return size, {"mode": mode, "words": words}


def parse_request_event_map_number(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {2: 4}, default=2)


def parse_battlefield_server_response_wait(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0x01: 4}, default=2)


def parse_adjust_entity_flags(data: bytes, pos: int) -> tuple[int, dict]:
    sizes = {
        0x00: 2,
        0x01: 2,
        0x02: 2,
        0x03: 2,
        0x04: 2,
        0x05: 2,
        0x06: 2,
        0x07: 2,
        0x08: 2,
        0x09: 2,
        0x0A: 2,
        0x0B: 2,
        0x0C: 2,
        0x0D: 2,
        0x0E: 2,
        0x0F: 2,
        0x10: 2,
        0x11: 4,
        0x12: 2,
        0x13: 2,
        0x14: 4,
        0x15: 4,
        0x16: 4,
        0x17: 4,
        0x18: 4,
        0x19: 2,
        0x1A: 2,
        0x1B: 6,
        0x1C: 6,
    }
    return _from_table(data, pos, sizes, default=2)


def parse_entity_status_handler(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0: 4, 1: 4, 2: 6, 3: 6, 4: 8}, default=4)


def parse_multi_purpose_entity_handler(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(
        data, pos, {0: 6, 1: 8, 2: 8, 3: 8, 4: 8, 5: 10, 6: 6, 7: 10, 8: 10}, default=2
    )


def parse_ui_window_string_handler(data: bytes, pos: int) -> tuple[int, dict]:
    sizes = {
        0x00: 20,
        0x01: 6,
        0x02: 6,
        0x03: 2,
        0x04: 6,
        0x05: 3,
        0x06: 3,
        0x07: 4,
        0x08: 2,
        0x09: 4,
        0x0A: 4,
        0x0B: 2,
        0x0C: 4,
        0x0D: 2,
        0x0E: 2,
        0x0F: 6,
        0x10: 6,
        0x11: 6,
        0x12: 6,
        0x13: 20,
        0x14: 12,
        0x15: 2,
    }
    return _from_table(data, pos, sizes, default=2)


def parse_entity_appearance_handler(data: bytes, pos: int) -> tuple[int, dict]:
    sizes = {
        0x00: 4,
        0x01: 4,
        0x02: 4,
        0x03: 4,
        0x04: 4,
        0x05: 4,
        0x06: 4,
        0x07: 4,
        0x08: 4,
        0x09: 4,
        0x0A: 4,
        0x0B: 20,
        0x0C: 6,
        0x0D: 14,
        0x0E: 14,
        0x0F: 4,
        0x10: 2,
        0x11: 2,
        0x12: 2,
        0x13: 2,
        0x14: 2,
        0x15: 2,
    }
    return _from_table(data, pos, sizes, default=2)


def parse_entity_data_handler(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {0x01: 10}, default=8)


def parse_party_state_check(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(data, pos, {1: 4, 2: 6}, default=2)


def parse_deprecated_ca(data: bytes, pos: int) -> tuple[int, dict]:
    return 1, {}


def parse_deprecated_cb(data: bytes, pos: int) -> tuple[int, dict]:
    return 1, {}


def parse_item_info_window_handler(data: bytes, pos: int) -> tuple[int, dict]:
    sizes = {
        0x00: 10,
        0x01: 10,
        0x02: 14,
        0x03: 10,
        0x10: 6,
        0x11: 4,
        0x20: 4,
    }
    return _from_table(data, pos, sizes, default=4)


def parse_map_query_window_handler(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(
        data, pos, {0x00: 9, 0x01: 32, 0x02: 9, 0x03: 30, 0x04: 30, 0x05: 30}, default=2
    )


def parse_set_entity_event_dir(data: bytes, pos: int) -> tuple[int, dict]:
    return _from_table(
        data, pos, {0x00: 6, 0x01: 8, 0x02: 8, 0x03: 8, 0x04: 12}, default=6
    )


# Stubs for opcodes whose real custom_parse lives in opcodes.py — the @op
# decorator there will overwrite the auto-generated registration. These are
# only here so opcodes_auto.py can look them up without KeyError.


def parse_update_player_location(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"mode": 0}
    mode = data[pos + 1]
    return (10 if mode == 0 else 2), {"mode": mode}


def parse_music_control(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 1, {"control": 0}
    control = data[pos + 1]
    long_form = bool(control & 0x80) or control >= 0xA0
    return (6 if long_form else 4), {"control": control}


def parse_crafting_handler(data: bytes, pos: int) -> tuple[int, dict]:
    if pos + 2 > len(data):
        return 2, {"mode": 0}
    mode = data[pos + 1]
    sizes = {0: 8, 1: 2, 2: 12, 3: 10, 4: 10, 5: 14}
    return sizes.get(mode, 2), {"mode": mode}


PARSERS: dict[int, Callable[[bytes, int], tuple[int, dict]]] = {
    0x1F: parse_move_entity,
    0x31: parse_update_entity_position,
    0x59: parse_update_entity_data_multi,
    0x5A: parse_update_event_position,
    0x5F: parse_multi_handler_complex,
    0x60: parse_adjust_render_flags1_multi,
    0x71: parse_handle_string_input,
    0x72: parse_load_event_weather,
    0x75: parse_load_room,
    0x79: parse_look_at_entity,
    0x7A: parse_vm_control,
    0x7E: parse_chocobo_mount_handler,
    0x87: parse_world_pass_handler_a,
    0x88: parse_world_pass_handler_b,
    0x9D: parse_string_handler_multi,
    0xA6: parse_request_event_map_number,
    0xA7: parse_battlefield_server_response_wait,
    0xAB: parse_adjust_entity_flags,
    0xAC: parse_entity_status_handler,
    0xAE: parse_multi_purpose_entity_handler,
    0xB4: parse_ui_window_string_handler,
    0xB6: parse_entity_appearance_handler,
    0xB7: parse_entity_data_handler,
    0xC2: parse_party_state_check,
    0xCA: parse_deprecated_ca,
    0xCB: parse_deprecated_cb,
    0xCC: parse_item_info_window_handler,
    0xD4: parse_map_query_window_handler,
    0xD8: parse_set_entity_event_dir,
    0x47: parse_update_player_location,
    0x5C: parse_music_control,
    0x8C: parse_crafting_handler,
}
