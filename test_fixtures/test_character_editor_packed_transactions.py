#!/usr/bin/env python3
"""Focused regression for byte-preserving packed Character Editor mutations."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_codecs import (
    BITSET_BLOB_SIZES,
    BITSET_MEANINGFUL_BITS,
    BLUE_SPELL_SLOT_COUNT,
    KEY_ITEM_TABLE_BYTES,
    MISSION_AREA_COUNT,
    MISSION_RECORD_SIZES,
    QUEST_AREA_COUNT,
    QUEST_RECORD_BYTES,
    QUEST_SET_BYTES,
)
from workbench.editors.character.packed_transactions import (
    _blue_spell_edit,
    _character_bitset_edit,
    _key_item_edit,
    _mission_edit,
    _quest_edit,
)


def mission_blob(family: str) -> bytes:
    record = MISSION_RECORD_SIZES[family]
    return bytes((index * 17 + 3) & 0xFF for index in range(record * MISSION_AREA_COUNT))


def quest_blob() -> bytes:
    return bytes((index * 11 + 9) & 0xFF for index in range(QUEST_AREA_COUNT * QUEST_RECORD_BYTES))


def keyitem_blob(family: str) -> bytes:
    tables = 8 if family == "lsb" else 7
    return bytes((index * 29 + 5) & 0xFF for index in range(tables * KEY_ITEM_TABLE_BYTES))


def bitset_blob(capability: str, family: str) -> bytes:
    size = BITSET_BLOB_SIZES[capability][family]
    return bytes((index * 13 + 7) & 0xFF for index in range(size))


def blue_spell_blob() -> bytes:
    return bytes((index * 7 + 1) & 0xFF for index in range(BLUE_SPELL_SLOT_COUNT))


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    return {index for index, (left, right) in enumerate(zip(before, after)) if left != right}


def main() -> None:
    before = mission_blob("dsp")
    record = MISSION_RECORD_SIZES["dsp"]
    area = 2
    after, old, new = _mission_edit(
        before,
        "dsp",
        {"area_id": area, "current": 321, "completed_id": 7, "completed": True},
    )
    start = area * record
    allowed = {start, start + 1, start + 2 + 7}
    assert changed_offsets(before, after).issubset(allowed)
    assert new["current"] == 321
    assert 7 in new["completed_ids"]

    try:
        _mission_edit(before, "dsp", {"area_id": 0, "status_upper": 1})
    except ValueError as exc:
        assert "does not contain" in str(exc)
    else:
        raise AssertionError("DSP accepted status_upper")

    for family in ("topaz", "lsb"):
        before = mission_blob(family)
        record = MISSION_RECORD_SIZES[family]
        area = 4
        start = area * record
        after, _, new = _mission_edit(
            before,
            family,
            {"area_id": area, "status_upper": 0x1122, "status_lower": 0x3344},
        )
        assert changed_offsets(before, after).issubset({start + 2, start + 3, start + 4, start + 5})
        assert new["status_upper"] == 0x1122
        assert new["status_lower"] == 0x3344

    # Quest mutations are identical across DSP/Topaz/LSB and touch exactly one target byte.
    for family in ("dsp", "topaz", "lsb"):
        before = quest_blob()
        for area_id, quest_id, state in ((0, 0, "current"), (5, 255, "current"), (10, 7, "completed"), (3, 248, "completed")):
            set_offset = 0 if state == "current" else QUEST_SET_BYTES
            byte_offset = area_id * QUEST_RECORD_BYTES + set_offset + quest_id // 8
            mask = 1 << (quest_id % 8)
            target = not bool(before[byte_offset] & mask)
            after, old, new = _quest_edit(
                before,
                family,
                {"area_id": area_id, "quest_id": quest_id, "state": state, "enabled": target},
            )
            assert changed_offsets(before, after).issubset({byte_offset})
            assert old == {"area_id": area_id, "quest_id": quest_id, "state": state, "enabled": (not target)}
            assert new == {"area_id": area_id, "quest_id": quest_id, "state": state, "enabled": target}

        invalid_cases = (
            ({"area_id": -1, "quest_id": 0, "state": "current", "enabled": True}, "area_id must be between"),
            ({"area_id": QUEST_AREA_COUNT, "quest_id": 0, "state": "current", "enabled": True}, "area_id must be between"),
            ({"area_id": 0, "quest_id": -1, "state": "current", "enabled": True}, "quest_id must be between"),
            ({"area_id": 0, "quest_id": 256, "state": "current", "enabled": True}, "quest_id must be between"),
            ({"area_id": 0, "quest_id": 1, "state": "unknown", "enabled": True}, "state must be either"),
            ({"area_id": 0, "quest_id": 1, "state": "current"}, "enabled must be supplied"),
        )
        for operation, expected in invalid_cases:
            try:
                _quest_edit(before, family, operation)
            except ValueError as exc:
                assert expected in str(exc)
            else:
                raise AssertionError(f"{family} accepted invalid quest edit {operation}")

    for family, key_item_id in (("dsp", 700), ("topaz", 1500), ("lsb", 3900)):
        before = keyitem_blob(family)
        table = key_item_id // 512
        bit = key_item_id % 512
        owned_offset = table * KEY_ITEM_TABLE_BYTES + bit // 8
        seen_offset = table * KEY_ITEM_TABLE_BYTES + 64 + bit // 8
        owned_target = not bool(before[owned_offset] & (1 << (bit % 8)))
        seen_target = not bool(before[seen_offset] & (1 << (bit % 8)))
        after, old, new = _key_item_edit(
            before,
            family,
            {"key_item_id": key_item_id, "owned": owned_target, "seen": seen_target},
        )
        assert changed_offsets(before, after).issubset({owned_offset, seen_offset})
        assert old["key_item_id"] == key_item_id
        assert new["owned"] is owned_target
        assert new["seen"] is seen_target

    for family in ("dsp", "topaz", "lsb"):
        before = blue_spell_blob()
        slot = 3
        after, old, new = _blue_spell_edit(before, family, {"slot": slot, "spell_id": 0x222})
        assert changed_offsets(before, after).issubset({slot})
        assert old["slot"] == slot
        assert new == {"slot": slot, "stored_value": 0x22, "spell_id": 0x222, "empty": False}

        cleared, clear_old, clear_new = _blue_spell_edit(after, family, {"slot": slot, "spell_id": None})
        assert changed_offsets(after, cleared).issubset({slot})
        assert clear_old["spell_id"] == 0x222
        assert clear_new == {"slot": slot, "stored_value": 0, "spell_id": None, "empty": True}

        duplicate_before = bytearray(before)
        duplicate_before[0] = 0x22
        duplicate_before[7] = 0x22
        duplicate_after, _, duplicate_new = _blue_spell_edit(
            bytes(duplicate_before), family, {"slot": 12, "spell_id": 0x222}
        )
        assert changed_offsets(bytes(duplicate_before), duplicate_after).issubset({12})
        assert duplicate_new["spell_id"] == 0x222
        zero_after, _, zero_new = _blue_spell_edit(duplicate_after, family, {"slot": 12, "spell_id": 0})
        assert zero_new["empty"] is True
        assert changed_offsets(duplicate_after, zero_after).issubset({12})

        for operation, expected in (
            ({"slot": -1, "spell_id": 0x201}, "slot must be between"),
            ({"slot": BLUE_SPELL_SLOT_COUNT, "spell_id": 0x201}, "slot must be between"),
            ({"slot": 0, "spell_id": 0x200}, "spell_id must be"),
            ({"slot": 0, "spell_id": 0x300}, "spell_id must be"),
        ):
            try:
                _blue_spell_edit(before, family, operation)
            except ValueError as exc:
                assert expected in str(exc)
            else:
                raise AssertionError(f"{family} accepted invalid blue-spell edit {operation}")

    cases = (
        ("abilities", "dsp", 16),
        ("abilities", "topaz", 200),
        ("abilities", "lsb", 390),
        ("weaponskills", "dsp", 48),
        ("weaponskills", "topaz", 1),
        ("weaponskills", "lsb", 63),
        ("titles", "dsp", 700),
        ("titles", "topaz", 1),
        ("titles", "lsb", 1100),
        ("visited_zones", "dsp", 230),
        ("visited_zones", "topaz", 33),
        ("visited_zones", "lsb", 300),
    )
    for capability, family, bit_id in cases:
        before = bitset_blob(capability, family)
        offset = bit_id // 8
        target = not bool(before[offset] & (1 << (bit_id % 8)))
        after, old, new = _character_bitset_edit(
            before,
            family,
            capability,
            {"bit_id": bit_id, "enabled": target},
        )
        assert changed_offsets(before, after).issubset({offset})
        assert old == {"bit_id": bit_id, "enabled": (not target)}
        assert new == {"bit_id": bit_id, "enabled": target}

    for family in ("dsp", "topaz"):
        before = bitset_blob("weaponskills", family)
        try:
            _character_bitset_edit(before, family, "weaponskills", {"bit_id": 49, "enabled": True})
        except ValueError as exc:
            assert "between 0 and 48" in str(exc)
        else:
            raise AssertionError(f"{family} accepted reserved learned-weaponskill bit 49")

    for capability in BITSET_BLOB_SIZES:
        for family in ("dsp", "topaz", "lsb"):
            invalid = BITSET_MEANINGFUL_BITS[capability][family]
            try:
                _character_bitset_edit(
                    bitset_blob(capability, family),
                    family,
                    capability,
                    {"bit_id": invalid, "enabled": True},
                )
            except ValueError as exc:
                assert "bit_id must be between" in str(exc)
            else:
                raise AssertionError(f"{family} {capability} accepted out-of-range bit {invalid}")


if __name__ == "__main__":
    main()
