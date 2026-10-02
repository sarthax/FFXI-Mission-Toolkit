#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_codecs import CAMPAIGN_BLOB_BYTES, decode_campaign
from workbench.editors.character.packed_transactions import _campaign_edit


def _blob() -> bytes:
    data = bytearray(CAMPAIGN_BLOB_BYTES)
    data[:2] = (17).to_bytes(2, "little")
    data[2 + 1] = 1
    data[2 + 255] = 1
    return bytes(data)


def main() -> None:
    for family in ("dsp", "topaz", "lsb"):
        original = _blob()

        changed, before, after = _campaign_edit(original, family, {"current": 321})
        assert before["current"] == 17 and after["current"] == 321
        assert changed[:2] == (321).to_bytes(2, "little")
        assert changed[2:] == original[2:]

        changed, before, after = _campaign_edit(original, family, {"completed_id": 0, "completed": True})
        assert before["completed"] is False and after["completed"] is True
        assert changed[2] == 1
        assert changed[:2] == original[:2]
        assert changed[3:] == original[3:]

        changed, before, after = _campaign_edit(original, family, {"completed_id": 511, "completed": True})
        assert before["completed"] is False and after["completed"] is True
        assert changed[2 + 511] == 1
        assert changed[:2 + 511] == original[:2 + 511]

        changed, _, after = _campaign_edit(original, family, {"current": 99, "completed_id": 255, "completed": False})
        decoded = decode_campaign(changed, family)
        assert after["current"] == 99
        assert after["completed"] is False
        assert decoded["current"] == 99
        assert 255 not in decoded["completed_ids"]
        expected = bytearray(original)
        expected[:2] = (99).to_bytes(2, "little")
        expected[2 + 255] = 0
        assert changed == bytes(expected)

        invalid = (
            ({"current": -1}, "current Campaign ID"),
            ({"current": 65536}, "current Campaign ID"),
            ({"completed_id": -1, "completed": True}, "completed_id"),
            ({"completed_id": 512, "completed": True}, "completed_id"),
            ({"completed_id": 7}, "completed must be supplied"),
            ({}, "At least one"),
        )
        for operation, message in invalid:
            try:
                _campaign_edit(original, family, operation)
            except ValueError as exc:
                assert message in str(exc)
            else:
                raise AssertionError(f"{family} accepted invalid Campaign operation: {operation}")


if __name__ == "__main__":
    main()
