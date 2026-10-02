#!/usr/bin/env python3
"""Focused regressions for lineage-aware Character Editor packed-state decoding."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_codecs import (
    KEY_ITEM_TABLE_BYTES,
    MISSION_AREA_COUNT,
    MISSION_RECORD_SIZES,
    PackedCodecError,
    decode_key_items,
    decode_missions,
)


def _mission_blob(family: str) -> bytes:
    record = MISSION_RECORD_SIZES[family]
    data = bytearray(record * MISSION_AREA_COUNT)
    # Area 3 / Zilart: current mission 17 and completion bits 0, 5, 63.
    start = 3 * record
    data[start : start + 2] = (17).to_bytes(2, "little")
    cursor = start + 2
    if family != "dsp":
        data[cursor : cursor + 2] = (0x1234).to_bytes(2, "little")
        data[cursor + 2 : cursor + 4] = (0x5678).to_bytes(2, "little")
        cursor += 4
    data[cursor + 0] = 1
    data[cursor + 5] = 1
    data[cursor + 63] = 1
    return bytes(data)


def _keyitem_blob(family: str) -> bytes:
    tables = 8 if family == "lsb" else 7
    data = bytearray(tables * KEY_ITEM_TABLE_BYTES)
    # Own IDs 0, 511, 512, and the highest bit available in this family.
    ids = [0, 511, 512, tables * 512 - 1]
    for key_item_id in ids:
        table = key_item_id // 512
        bit = key_item_id % 512
        base = table * KEY_ITEM_TABLE_BYTES
        data[base + bit // 8] |= 1 << (bit % 8)
        # Mark the same key item as seen in the second 64-byte set.
        data[base + 64 + bit // 8] |= 1 << (bit % 8)
    return bytes(data)


def main() -> None:
    dsp = decode_missions(_mission_blob("dsp"), "dsp")
    assert dsp["layout"] == "dsp-missionlog-v1"
    assert dsp["blob_bytes"] == 990
    assert dsp["areas"][3]["name"] == "Rise of the Zilart"
    assert dsp["areas"][3]["current"] == 17
    assert dsp["areas"][3]["status_upper"] is None
    assert dsp["areas"][3]["completed_ids"] == [0, 5, 63]
    assert dsp["write_enabled"] is False

    topaz = decode_missions(_mission_blob("topaz"), "topaz")
    assert topaz["layout"] == "topaz-lsb-missionlog-v2"
    assert topaz["blob_bytes"] == 1050
    assert topaz["areas"][3]["status_upper"] == 0x1234
    assert topaz["areas"][3]["status_lower"] == 0x5678

    lsb = decode_missions(_mission_blob("lsb"), "lsb")
    assert lsb["record_size"] == 70
    assert lsb["areas"][3]["completed_count"] == 3

    for family, count in (("dsp", 7), ("topaz", 7), ("lsb", 8)):
        decoded = decode_key_items(_keyitem_blob(family), family)
        assert decoded["table_count"] == count
        assert decoded["blob_bytes"] == count * 128
        assert decoded["owned_ids"] == [0, 511, 512, count * 512 - 1]
        assert decoded["seen_ids"] == decoded["owned_ids"]
        assert decoded["write_enabled"] is False

    try:
        decode_missions(bytes(1050), "dsp")
    except PackedCodecError as exc:
        assert "does not match dsp layout" in str(exc)
    else:
        raise AssertionError("DSP mission decoder accepted Topaz/LSB-sized data")

    try:
        decode_key_items(bytes(896), "lsb")
    except PackedCodecError as exc:
        assert "does not match lsb layout" in str(exc)
    else:
        raise AssertionError("LSB key-item decoder accepted DSP/Topaz-sized data")


if __name__ == "__main__":
    main()
