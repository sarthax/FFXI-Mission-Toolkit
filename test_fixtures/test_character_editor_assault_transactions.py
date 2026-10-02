#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_transactions import _assault_edit


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    return {index for index, (left, right) in enumerate(zip(before, after)) if left != right}


def assault_blob() -> bytes:
    data = bytearray(130)
    data[0:2] = (7).to_bytes(2, "little")
    data[2 + 1] = 1
    data[2 + 127] = 1
    return bytes(data)


def main() -> None:
    for family in ("dsp", "topaz", "lsb"):
        before = assault_blob()

        after, old, new = _assault_edit(before, family, {"current": 52})
        assert changed_offsets(before, after).issubset({0, 1})
        assert old["current"] == 7
        assert new["current"] == 52

        after, old, new = _assault_edit(before, family, {"completed_id": 0, "completed": True})
        assert changed_offsets(before, after).issubset({2})
        assert old["completed_id"] == 0 and old["completed"] is False
        assert new["completed"] is True

        after, old, new = _assault_edit(before, family, {"completed_id": 127, "completed": False})
        assert changed_offsets(before, after).issubset({129})
        assert old["completed"] is True
        assert new["completed"] is False

        after, _, new = _assault_edit(before, family, {"current": 51, "completed_id": 1, "completed": False})
        assert changed_offsets(before, after).issubset({0, 1, 3})
        assert new["current"] == 51 and new["completed"] is False

        invalid = (
            ({}, "At least one"),
            ({"current": -1}, "current Assault ID"),
            ({"current": 65536}, "current Assault ID"),
            ({"completed_id": -1, "completed": True}, "completed_id"),
            ({"completed_id": 128, "completed": True}, "completed_id"),
            ({"completed_id": 1}, "completed must be supplied"),
        )
        for operation, expected in invalid:
            try:
                _assault_edit(before, family, operation)
            except ValueError as exc:
                assert expected in str(exc)
            else:
                raise AssertionError(f"{family} accepted invalid Assault edit {operation}")


if __name__ == "__main__":
    main()
