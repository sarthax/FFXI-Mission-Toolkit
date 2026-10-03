#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.eminence_codec import (
    EMINENCE_ACTIVE_BYTES,
    EMINENCE_BLOB_BYTES,
    EMINENCE_COMPLETE_OFFSET,
    EMINENCE_PROGRESS_OFFSET,
    EminenceCodecError,
    decode_eminence,
)
from workbench.editors.character.eminence_transactions import _edit_blob


def _blob() -> bytes:
    data = bytearray(EMINENCE_BLOB_BYTES)
    data[0:2] = (1).to_bytes(2, "little")
    data[EMINENCE_ACTIVE_BYTES:EMINENCE_PROGRESS_OFFSET] = b"\xAA\x55"
    data[EMINENCE_PROGRESS_OFFSET:EMINENCE_PROGRESS_OFFSET + 4] = (10).to_bytes(4, "little")
    data[EMINENCE_COMPLETE_OFFSET + 5 // 8] |= 1 << (5 % 8)
    return bytes(data)


def _changed_indices(before: bytes, after: bytes) -> set[int]:
    return {index for index, (left, right) in enumerate(zip(before, after)) if left != right}


def main() -> None:
    for family in ("topaz", "lsb"):
        original = _blob()

        changed, before, after = _edit_blob(
            original,
            family,
            {"kind": "active_slot", "slot": 30, "record_id": 4095, "progress": 0xDEADBEEF},
        )
        assert before["slot"] == 30 and before["empty"] is True
        assert after["record_id"] == 4095
        assert after["progress"] == 0xDEADBEEF
        expected = bytearray(original)
        expected[60:62] = (4095).to_bytes(2, "little")
        p30 = EMINENCE_PROGRESS_OFFSET + 30 * 4
        expected[p30:p30 + 4] = (0xDEADBEEF).to_bytes(4, "little")
        assert changed == bytes(expected)
        assert changed[EMINENCE_ACTIVE_BYTES:EMINENCE_PROGRESS_OFFSET] == b"\xAA\x55"

        changed, before, after = _edit_blob(
            original,
            family,
            {"kind": "active_slot", "slot": 0, "record_id": 0, "progress": 0},
        )
        assert before["record_id"] == 1 and before["progress"] == 10
        assert after["empty"] is True and after["progress"] == 0
        assert _changed_indices(original, changed).issubset({0, 1, EMINENCE_PROGRESS_OFFSET, EMINENCE_PROGRESS_OFFSET + 1, EMINENCE_PROGRESS_OFFSET + 2, EMINENCE_PROGRESS_OFFSET + 3})

        changed, before, after = _edit_blob(
            original,
            family,
            {"kind": "completion", "record_id": 0, "completed": True},
        )
        assert before == {"record_id": 0, "completed": False}
        assert after == {"record_id": 0, "completed": True}
        assert _changed_indices(original, changed) == {EMINENCE_COMPLETE_OFFSET}

        changed, before, after = _edit_blob(
            original,
            family,
            {"kind": "completion", "record_id": 4095, "completed": True},
        )
        assert before["completed"] is False and after["completed"] is True
        assert _changed_indices(original, changed) == {EMINENCE_COMPLETE_OFFSET + 511}
        decoded = decode_eminence(changed, family)
        assert 4095 in decoded["completed_ids"]

        invalid = (
            ({"kind": "active_slot", "slot": -1, "record_id": 1, "progress": 0}, "slot must be"),
            ({"kind": "active_slot", "slot": 31, "record_id": 1, "progress": 0}, "slot must be"),
            ({"kind": "active_slot", "slot": 0, "record_id": 1}, "require both"),
            ({"kind": "active_slot", "slot": 0, "record_id": 0, "progress": 1}, "must also have progress 0"),
            ({"kind": "active_slot", "slot": 0, "record_id": 65536, "progress": 0}, "record_id must be"),
            ({"kind": "active_slot", "slot": 0, "record_id": 1, "progress": 4294967296}, "progress must be"),
            ({"kind": "completion", "record_id": -1, "completed": True}, "record_id must be"),
            ({"kind": "completion", "record_id": 4096, "completed": True}, "record_id must be"),
            ({"kind": "completion", "record_id": 1}, "require completed"),
            ({"kind": "unknown"}, "kind must be"),
        )
        for operation, message in invalid:
            try:
                _edit_blob(original, family, operation)
            except ValueError as exc:
                assert message in str(exc)
            else:
                raise AssertionError(f"{family} accepted invalid Eminence operation: {operation}")

    try:
        _edit_blob(_blob(), "dsp", {"kind": "completion", "record_id": 1, "completed": True})
    except EminenceCodecError:
        pass
    else:
        raise AssertionError("DSP Eminence mutation should remain unsupported")


if __name__ == "__main__":
    main()
