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
    BITSET_BLOB_SIZES,
    BITSET_MEANINGFUL_BITS,
    BLUE_SPELL_ID_OFFSET,
    BLUE_SPELL_SLOT_COUNT,
    KEY_ITEM_TABLE_BYTES,
    MISSION_AREA_COUNT,
    MISSION_RECORD_SIZES,
    QUEST_AREA_COUNT,
    QUEST_RECORD_BYTES,
    QUEST_SET_BYTES,
    PackedCodecError,
    decode_blue_spells,
    decode_character_bitset,
    decode_key_items,
    decode_missions,
    decode_packed_field,
    decode_quests,
)


def _mission_blob(family: str) -> bytes:
    record = MISSION_RECORD_SIZES[family]
    data = bytearray(record * MISSION_AREA_COUNT)
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


def _quest_blob() -> bytes:
    data = bytearray(QUEST_AREA_COUNT * QUEST_RECORD_BYTES)
    # Jeuno area 3: current IDs 0, 17, 255; completed IDs 1, 42, 254.
    start = 3 * QUEST_RECORD_BYTES
    for quest_id in (0, 17, 255):
        data[start + quest_id // 8] |= 1 << (quest_id % 8)
    complete = start + QUEST_SET_BYTES
    for quest_id in (1, 42, 254):
        data[complete + quest_id // 8] |= 1 << (quest_id % 8)
    # Coalition area 10 high edge coverage.
    start = 10 * QUEST_RECORD_BYTES
    data[start + 31] |= 0x80
    data[start + QUEST_SET_BYTES] |= 0x01
    return bytes(data)


def _keyitem_blob(family: str) -> bytes:
    tables = 8 if family == "lsb" else 7
    data = bytearray(tables * KEY_ITEM_TABLE_BYTES)
    ids = [0, 511, 512, tables * 512 - 1]
    for key_item_id in ids:
        table = key_item_id // 512
        bit = key_item_id % 512
        base = table * KEY_ITEM_TABLE_BYTES
        data[base + bit // 8] |= 1 << (bit % 8)
        data[base + 64 + bit // 8] |= 1 << (bit % 8)
    return bytes(data)


def _bitset_blob(capability: str, family: str, ids: list[int]) -> bytes:
    data = bytearray(BITSET_BLOB_SIZES[capability][family])
    for bit_id in ids:
        data[bit_id // 8] |= 1 << (bit_id % 8)
    return bytes(data)


def _blue_spell_blob() -> bytes:
    data = bytearray(BLUE_SPELL_SLOT_COUNT)
    data[0] = 1
    data[3] = 0x22
    data[7] = 1
    data[19] = 0xFF
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

    # Quest layout is byte-for-byte identical across DSP, Topaz and LSB.
    for family in ("dsp", "topaz", "lsb"):
        quests = decode_quests(_quest_blob(), family)
        assert quests["layout"] == "dsp-topaz-lsb-questlog-11x256x2"
        assert quests["blob_bytes"] == 704
        assert quests["record_size"] == 64
        assert quests["area_count"] == 11
        assert quests["bits_per_set"] == 256
        assert quests["areas"][3]["name"] == "Jeuno"
        assert quests["areas"][3]["current_ids"] == [0, 17, 255]
        assert quests["areas"][3]["completed_ids"] == [1, 42, 254]
        assert quests["areas"][3]["current_count"] == 3
        assert quests["areas"][3]["completed_count"] == 3
        assert quests["areas"][10]["name"] == "Coalition"
        assert quests["areas"][10]["current_ids"] == [255]
        assert quests["areas"][10]["completed_ids"] == [0]
        assert quests["write_enabled"] is False
        via_dispatch = decode_packed_field("quests", _quest_blob(), family)
        assert via_dispatch is not None and via_dispatch["areas"] == quests["areas"]

    for family, count in (("dsp", 7), ("topaz", 7), ("lsb", 8)):
        decoded = decode_key_items(_keyitem_blob(family), family)
        assert decoded["table_count"] == count
        assert decoded["blob_bytes"] == count * 128
        assert decoded["owned_ids"] == [0, 511, 512, count * 512 - 1]
        assert decoded["seen_ids"] == decoded["owned_ids"]
        assert decoded["write_enabled"] is False

    for family in ("dsp", "topaz", "lsb"):
        decoded = decode_blue_spells(_blue_spell_blob(), family)
        assert decoded["layout"] == "dsp-topaz-lsb-blue-spell-slots-v1"
        assert decoded["blob_bytes"] == BLUE_SPELL_SLOT_COUNT
        assert decoded["slot_count"] == 20
        assert decoded["spell_id_offset"] == 0x200
        assert decoded["set_spell_ids"] == [0x201, 0x222, 0x201, 0x2FF]
        assert decoded["set_count"] == 4
        assert decoded["slots"][0] == {"slot": 0, "stored_value": 1, "spell_id": 0x201, "empty": False}
        assert decoded["slots"][1] == {"slot": 1, "stored_value": 0, "spell_id": None, "empty": True}
        assert decoded["slots"][19]["spell_id"] == BLUE_SPELL_ID_OFFSET + 0xFF
        assert decoded["write_enabled"] is False
        via_dispatch = decode_packed_field("blue_spells", _blue_spell_blob(), family)
        assert via_dispatch is not None and via_dispatch["slots"] == decoded["slots"]

    for family in ("dsp", "topaz", "lsb"):
        last = BITSET_MEANINGFUL_BITS["abilities"][family] - 1
        decoded = decode_character_bitset("abilities", _bitset_blob("abilities", family, [0, 9, last]), family)
        assert decoded["set_ids"] == [0, 9, last]
        assert decoded["reserved_set_ids"] == []
        assert decoded["blob_bytes"] == BITSET_BLOB_SIZES["abilities"][family]
        assert decoded["write_enabled"] is False

    for capability in ("titles", "visited_zones"):
        for family in ("dsp", "topaz", "lsb"):
            last = BITSET_MEANINGFUL_BITS[capability][family] - 1
            decoded = decode_packed_field(capability, _bitset_blob(capability, family, [1, last]), family)
            assert decoded is not None
            assert decoded["set_ids"] == [1, last]
            assert decoded["storage_bits"] == BITSET_BLOB_SIZES[capability][family] * 8
            assert decoded["meaningful_bits"] == decoded["storage_bits"]

    for family in ("dsp", "topaz"):
        decoded = decode_character_bitset("weaponskills", _bitset_blob("weaponskills", family, [0, 48, 63]), family)
        assert decoded["layout"] == "dsp-topaz-learned-weaponskills-49-in-64"
        assert decoded["set_ids"] == [0, 48]
        assert decoded["reserved_set_ids"] == [63]
        assert decoded["meaningful_bits"] == 49
        assert decoded["storage_bits"] == 64

    lsb_ws = decode_character_bitset("weaponskills", _bitset_blob("weaponskills", "lsb", [0, 48, 63]), "lsb")
    assert lsb_ws["layout"] == "lsb-learned-weaponskills-64"
    assert lsb_ws["set_ids"] == [0, 48, 63]
    assert lsb_ws["reserved_set_ids"] == []

    try:
        decode_missions(bytes(1050), "dsp")
    except PackedCodecError as exc:
        assert "does not match dsp layout" in str(exc)
    else:
        raise AssertionError("DSP mission decoder accepted Topaz/LSB-sized data")

    for family in ("dsp", "topaz", "lsb"):
        try:
            decode_quests(bytes(QUEST_AREA_COUNT * QUEST_RECORD_BYTES - 1), family)
        except PackedCodecError as exc:
            assert f"does not match {family} layout" in str(exc)
        else:
            raise AssertionError(f"{family} quest decoder accepted a 703-byte BLOB")

    try:
        decode_key_items(bytes(896), "lsb")
    except PackedCodecError as exc:
        assert "does not match lsb layout" in str(exc)
    else:
        raise AssertionError("LSB key-item decoder accepted DSP/Topaz-sized data")

    for family in ("dsp", "topaz", "lsb"):
        try:
            decode_blue_spells(bytes(BLUE_SPELL_SLOT_COUNT - 1), family)
        except PackedCodecError as exc:
            assert f"does not match {family} layout" in str(exc)
        else:
            raise AssertionError(f"{family} blue-spell decoder accepted a 19-byte slot array")

    try:
        decode_character_bitset("titles", bytes(BITSET_BLOB_SIZES["lsb"]["titles"]), "dsp")
    except PackedCodecError as exc:
        assert "does not match dsp layout" in str(exc)
    else:
        raise AssertionError("DSP title decoder accepted LSB-sized data")

    try:
        decode_character_bitset("abilities", bytes(BITSET_BLOB_SIZES["dsp"]["abilities"]), "lsb")
    except PackedCodecError as exc:
        assert "does not match lsb layout" in str(exc)
    else:
        raise AssertionError("LSB ability decoder accepted DSP/Topaz-sized data")


if __name__ == "__main__":
    main()
