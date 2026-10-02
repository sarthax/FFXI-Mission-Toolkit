#!/usr/bin/env python3
"""Focused regression for byte-preserving packed Character Editor mutations."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_codecs import KEY_ITEM_TABLE_BYTES, MISSION_AREA_COUNT, MISSION_RECORD_SIZES
from workbench.editors.character.packed_transactions import _key_item_edit, _mission_edit


def mission_blob(family: str) -> bytes:
    record = MISSION_RECORD_SIZES[family]
    return bytes((index * 17 + 3) & 0xFF for index in range(record * MISSION_AREA_COUNT))


def keyitem_blob(family: str) -> bytes:
    tables = 8 if family == "lsb" else 7
    return bytes((index * 29 + 5) & 0xFF for index in range(tables * KEY_ITEM_TABLE_BYTES))


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    return {index for index, (left, right) in enumerate(zip(before, after)) if left != right}


def main() -> None:
    # DSP mission: current and one completion flag only touch those exact bytes.
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

    # DSP must never accept Topaz/LSB-only status fields.
    try:
        _mission_edit(before, "dsp", {"area_id": 0, "status_upper": 1})
    except ValueError as exc:
        assert "does not contain" in str(exc)
    else:
        raise AssertionError("DSP accepted status_upper")

    # Topaz and LSB status words are independently writable without touching neighboring areas.
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

    # Key-item mutation may alter only the target owned/seen bytes.
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


if __name__ == "__main__":
    main()
