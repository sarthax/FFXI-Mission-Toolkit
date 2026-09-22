"""Decode FFXI work-area addresses into luaparser AST nodes.

Address ranges and how they render:
    0x0000-0x004F   scratch[N]                  per-event scratchpad
    0x1000          result                      primary dialog selection
    0x1001          result2                     secondary scratch / state
    0x1002-0x1009   params[0..7]                event input parameters
    0x100A-0x105F   state[N]                    zone-persistent state
    0x1100-0x115F   saved[N]                    save/restore snapshot buffer
    0x1700-0x175F   state2[N]                   secondary zone-persistent block
    0x7Fxx          Player_X, EventDir, ...     read-only entity/player slots
    0x8000-0x8FFF   <literal>                   immediate-data reference (via imed)
"""

from __future__ import annotations

import re

from luaparser import astnodes as N

_WORKLOCAL_MAX = 80
_WORK_ZONE_BASE = 4096
_WORK_ZONE_MEMORIZE_BASE = 4352
_WORK_ZONE_1700_BASE = 5888
_WORK_ZONE_SLOTS = 96
_IMED_BASE = 0x8000
_IMED_MAX = 0x8FFF

_NAMED_WORK_ZONE = {0: "result", 1: "result2"}

_SPECIAL_SLOTS = {
    0x7F00: "EventPos_X",
    0x7F01: "EventPos_Z",
    0x7F02: "EventPos_Y",
    0x7F03: "EventDir",
    0x7F06: "Entity_JobId",
    0x7F07: "Entity_Race",
    0x7F08: "Entity_JobLevel",
    0x7F0A: "Entity_ServerId",
    0x7F80: "Player_X",
    0x7F81: "Player_Z",
    0x7F82: "Player_Y",
    0x7F83: "Player_Dir",
    0x7F86: "Player_JobId",
    0x7F87: "Player_Race",
    0x7F88: "Player_JobLevel",
    0x7F8A: "Player_ServerId",
}

_LUA_IDENT_BAD = re.compile(r"[^A-Za-z0-9_]")


def value(addr: int, imed: list[int] | None) -> N.Expression:
    if _IMED_BASE <= addr <= _IMED_MAX:
        idx = addr & 0x7FFF
        if imed is not None and idx < len(imed):
            return N.Number(imed[idx])
        return _index("References", idx)

    if addr < 2048:
        return _index("scratch", addr) if addr < _WORKLOCAL_MAX else _invalid(addr)

    if addr < _WORK_ZONE_MEMORIZE_BASE:
        slot = addr - _WORK_ZONE_BASE
        if slot in _NAMED_WORK_ZONE:
            return N.Name(_NAMED_WORK_ZONE[slot])
        if 2 <= slot <= 9:
            return _index("params", slot - 2)
        if 0 <= slot < _WORK_ZONE_SLOTS:
            return _index("state", slot)
        return _invalid(addr)

    if addr < 4608:
        slot = addr - _WORK_ZONE_MEMORIZE_BASE
        return _index("saved", slot) if 0 <= slot < _WORK_ZONE_SLOTS else _invalid(addr)

    if addr < 6144:
        slot = addr - _WORK_ZONE_1700_BASE
        return (
            _index("state2", slot) if 0 <= slot < _WORK_ZONE_SLOTS else _invalid(addr)
        )

    if addr in _SPECIAL_SLOTS:
        return N.Name(_SPECIAL_SLOTS[addr])

    return N.Name(f"val_0x{addr:04X}")


def entity(
    entity_id: int, names: dict[int, str] | None = None, self_id: int | None = None
) -> N.Expression:
    if entity_id in (0x7FFFFFC0, 0x7FFFFFF0, 0x7FFFFFF9):
        return N.Name("player")
    # 0x7FFFFFF8 is the EventEntity sentinel; some scripts hardcode the
    # actor's specific id instead, which means the same thing.
    if entity_id == 0x7FFFFFF8 or (self_id is not None and entity_id == self_id):
        return N.Name("npc")
    if 0x7FFFFFC1 <= entity_id <= 0x7FFFFFC5:
        return N.Name(f"party{entity_id - 0x7FFFFFC0}")
    if names and entity_id in names:
        return N.Name(_safe_ident(names[entity_id]))
    return N.Name(f"entity_0x{entity_id:08X}")


def action_id(value: int) -> str:
    """4-byte packed-ASCII action id, e.g. 0x306B6C74 -> "tlk0"."""
    bs = (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF)
    if all(0x20 <= b <= 0x7E for b in bs):
        return bytes(bs).decode("ascii")
    return f"0x{value:08X}"


def coord_float(raw: int) -> float:
    """FFXI coords are signed-32 fixed-point, *0.001."""
    if raw > 0x7FFFFFFF:
        raw -= 0x100000000
    return raw * 0.001


def yaw_byte(raw: int) -> int:
    """FFXI direction byte (0..255). Bytecode stores 12-bit (0..4095), so /16."""
    return (raw & 0xFFFF) // 16


def lua_string(s: str) -> N.String:
    return N.String(s=s, raw=s, delimiter=N.StringDelimiter.DOUBLE_QUOTE)


def _index(table: str, idx: int) -> N.Index:
    return N.Index(
        idx=N.Number(idx), value=N.Name(table), notation=N.IndexNotation.SQUARE
    )


def _invalid(addr: int) -> N.Name:
    return N.Name(f"bad_addr_0x{addr:04X}")


def _safe_ident(name: str) -> str:
    s = _LUA_IDENT_BAD.sub("_", name)
    if s and s[0].isdigit():
        s = "_" + s
    return s or "_unknown"
