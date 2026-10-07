#!/usr/bin/env python3
"""Regression for large PacketViewer provenance parsing."""
from workbench.captures.ingestion import build_index as bci

BLOCK = """[{ts}] 
        |  0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F      | 0123456789ABCDEF
    -----------------------------------------------------  ----------------------
      0 | 08 1A 03 00 FE FF FF FF -- -- -- -- -- -- -- --    0 | ................
"""

text = "\n".join([
    BLOCK.format(ts="2025-05-01 23:23:51"),
    BLOCK.format(ts="2025-05-01 23:23:52"),
    BLOCK.format(ts="2025-05-01 23:23:53"),
])
rows = bci.parse_packetlogger_records(text, "0x00E")
assert len(rows) == 3, rows
assert [r["ts"] for r in rows] == [
    "2025-05-01 23:23:51", "2025-05-01 23:23:52", "2025-05-01 23:23:53"
]
assert rows[0]["start_line"] == 1
assert rows[1]["start_line"] > rows[0]["start_line"]
assert rows[2]["start_line"] > rows[1]["start_line"]
assert all(r["end_line"] >= r["start_line"] for r in rows)

unicode_text = "Aé中B"
positions = [0, 1, 2, 3, 4]
offsets = bci._utf8_offsets_for_positions(unicode_text, positions)
for pos in positions:
    assert offsets[pos] == len(unicode_text[:pos].encode("utf-8")), (pos, offsets[pos])

# A moderately large synthetic stream exercises the linear indexing path without imposing
# a fragile wall-clock threshold on CI.
large = "\n".join(BLOCK.format(ts=f"2025-05-01 23:{i // 60:02d}:{i % 60:02d}") for i in range(3000))
large_rows = bci.parse_packetlogger_records(large, "0x00E")
assert len(large_rows) == 3000
print("PacketViewer provenance regression passed")
