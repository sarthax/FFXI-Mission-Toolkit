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
    EMINENCE_ACTIVE_SLOTS,
    EMINENCE_BLOB_BYTES,
    EMINENCE_COMPLETE_OFFSET,
    EMINENCE_PROGRESS_OFFSET,
    EminenceCodecError,
    decode_eminence,
)


def _blob() -> bytes:
    data = bytearray(EMINENCE_BLOB_BYTES)
    # Active slot 0 and the special time-limited slot 30.
    data[0:2] = (1).to_bytes(2, "little")
    data[30 * 2 : 30 * 2 + 2] = (4095).to_bytes(2, "little")
    # Preserve/observe native alignment padding.
    data[EMINENCE_ACTIVE_BYTES:EMINENCE_PROGRESS_OFFSET] = b"\xAA\x55"
    data[EMINENCE_PROGRESS_OFFSET : EMINENCE_PROGRESS_OFFSET + 4] = (123456).to_bytes(4, "little")
    p30 = EMINENCE_PROGRESS_OFFSET + 30 * 4
    data[p30 : p30 + 4] = (0xDEADBEEF).to_bytes(4, "little")
    # Completion bitmap records 0 and 4095.
    data[EMINENCE_COMPLETE_OFFSET] |= 0x01
    data[EMINENCE_COMPLETE_OFFSET + 511] |= 0x80
    return bytes(data)


def main() -> None:
    for family in ("topaz", "lsb"):
        decoded = decode_eminence(_blob(), family)
        assert decoded["layout"] == "topaz-lsb-eminencelog-native-v1"
        assert decoded["blob_bytes"] == 700
        assert decoded["active_slot_count"] == EMINENCE_ACTIVE_SLOTS == 31
        assert decoded["active_count"] == 2
        assert decoded["active"][0]["record_id"] == 1
        assert decoded["active"][0]["progress"] == 123456
        assert decoded["active"][0]["time_limited"] is False
        assert decoded["active"][30]["record_id"] == 4095
        assert decoded["active"][30]["progress"] == 0xDEADBEEF
        assert decoded["active"][30]["time_limited"] is True
        assert decoded["padding_offset"] == 62
        assert decoded["padding_bytes"] == 2
        assert decoded["padding_hex"] == "aa55"
        assert decoded["progress_offset"] == 64
        assert decoded["complete_offset"] == 188
        assert decoded["completion_bits"] == 4096
        assert decoded["completed_ids"] == [0, 4095]
        assert decoded["completed_count"] == 2
        assert decoded["write_enabled"] is False

        try:
            decode_eminence(bytes(EMINENCE_BLOB_BYTES - 1), family)
        except EminenceCodecError as exc:
            assert f"does not match {family} layout" in str(exc)
        else:
            raise AssertionError(f"{family} Eminence decoder accepted a 699-byte BLOB")

    try:
        decode_eminence(_blob(), "dsp")
    except EminenceCodecError as exc:
        assert "Legacy DSP has no verified chars.eminence" in str(exc)
    else:
        raise AssertionError("DSP Eminence decoder should be explicitly unsupported")


if __name__ == "__main__":
    main()
