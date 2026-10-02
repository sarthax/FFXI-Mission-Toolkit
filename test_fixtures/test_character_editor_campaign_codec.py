#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.packed_codecs import (
    CAMPAIGN_BLOB_BYTES,
    CAMPAIGN_COMPLETE_COUNT,
    PackedCodecError,
    decode_campaign,
    decode_packed_field,
)


def _blob() -> bytes:
    data = bytearray(CAMPAIGN_BLOB_BYTES)
    data[:2] = (321).to_bytes(2, "little")
    for campaign_id in (0, 1, 255, 511):
        data[2 + campaign_id] = 1
    return bytes(data)


def main() -> None:
    for family in ("dsp", "topaz", "lsb"):
        decoded = decode_campaign(_blob(), family)
        assert decoded["layout"] == "dsp-topaz-lsb-campaignlog-v1"
        assert decoded["blob_bytes"] == 514
        assert decoded["current"] == 321
        assert decoded["complete_slots"] == CAMPAIGN_COMPLETE_COUNT == 512
        assert decoded["completed_ids"] == [0, 1, 255, 511]
        assert decoded["completed_count"] == 4
        assert decoded["write_enabled"] is False

        via_dispatch = decode_packed_field("campaign", _blob(), family)
        assert via_dispatch is not None
        assert via_dispatch["completed_ids"] == [0, 1, 255, 511]

        try:
            decode_campaign(bytes(CAMPAIGN_BLOB_BYTES - 1), family)
        except PackedCodecError as exc:
            assert f"does not match {family} layout" in str(exc)
        else:
            raise AssertionError(f"{family} Campaign decoder accepted a 513-byte BLOB")


if __name__ == "__main__":
    main()
