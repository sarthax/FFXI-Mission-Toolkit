"""Pure-Python builder/parser for the incoming 0x028 action packets used by animprobe.

Bit offsets are packet-relative (header included) and were validated against real
Mumor captures (skill 2900/anim 2038). No I/O, so it is unit-testable anywhere.
"""
from __future__ import annotations

# Real captured category-11 (NPC TP finish) packet: Mumor 17093309, skill 2900, anim 2038.
FINISH_TEMPLATE_HEX = (
    "28 14 91 1c 1f bd d2 04 01 01 2c d5 02 00 00 00 00 00 00 c0 87 02 40 60 fb 03 74 04 "
    "40 2e 00 00 00 00 00 31 09 39 38 00"
)
# Real captured category-7 ("readies") packet from the same capture, param 24931.
READY_TEMPLATE_HEX = (
    "28 14 13 1e 1f bd d2 04 01 01 dc 58 18 5d 19 00 00 00 00 c0 87 02 40 00 fe 10 81 6a "
    "c1 0a 00 00 00 00 00 00 00 00 00 02"
)

ACTOR_BIT, ACTOR_BITS = 40, 32      # bytes 5-8
CATEGORY_BIT, CATEGORY_BITS = 82, 4
PARAM_BIT, PARAM_BITS = 86, 16       # skill id (finish) / 24931 (ready)
TARGET_BIT, TARGET_BITS = 150, 32
ANIM_BIT, ANIM_BITS = 191, 12


def _to_int(b: bytes) -> int:
    return int.from_bytes(b, "little")


def get_bits(packet: bytes, start: int, n: int) -> int:
    return (_to_int(packet) >> start) & ((1 << n) - 1)


def set_bits(packet: bytes, start: int, n: int, value: int) -> bytes:
    if value < 0 or value >= (1 << n):
        raise ValueError(f"value {value} does not fit in {n} bits")
    v = _to_int(packet)
    v = (v & ~(((1 << n) - 1) << start)) | (value << start)
    return v.to_bytes(len(packet), "little")


def _template(hexstr: str) -> bytes:
    return bytes.fromhex(hexstr.replace(" ", ""))


def build_finish(actor: int, target: int, anim: int, skill: int) -> bytes:
    p = _template(FINISH_TEMPLATE_HEX)
    p = set_bits(p, ACTOR_BIT, ACTOR_BITS, actor)
    p = set_bits(p, TARGET_BIT, TARGET_BITS, target)
    p = set_bits(p, PARAM_BIT, PARAM_BITS, skill)
    return set_bits(p, ANIM_BIT, ANIM_BITS, anim)


def build_ready(actor: int) -> bytes:
    return set_bits(_template(READY_TEMPLATE_HEX), ACTOR_BIT, ACTOR_BITS, actor)


def parse(packet: bytes) -> dict:
    return {
        "actor": get_bits(packet, ACTOR_BIT, ACTOR_BITS),
        "category": get_bits(packet, CATEGORY_BIT, CATEGORY_BITS),
        "param": get_bits(packet, PARAM_BIT, PARAM_BITS),
        "target": get_bits(packet, TARGET_BIT, TARGET_BITS),
        "anim": get_bits(packet, ANIM_BIT, ANIM_BITS),
    }
