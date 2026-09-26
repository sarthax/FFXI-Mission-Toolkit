#!/usr/bin/env python3
"""Binary probes persist as capability observations: hit=VERIFIED, miss=UNKNOWN, rerun idempotent."""
import struct, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workbench.core import graph
from workbench.client.binary_probes import persist_probes


def tiny_pe(payload: bytes) -> bytes:
    """Minimal PE32 with one .data section holding payload."""
    dos = b"MZ" + b"\0" * 58 + struct.pack("<I", 64)
    coff = b"PE\0\0" + struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, 224, 0x2102)
    opt = struct.pack("<H", 0x10B) + b"\0" * 26 + struct.pack("<I", 0x400000) + struct.pack("<II", 0x1000, 0x200)
    opt = opt.ljust(56, b"\0") + struct.pack("<II", 0x2000, 0x200) + b"\0" * 8 + struct.pack("<I", 16)
    opt = opt.ljust(224, b"\0")
    sec = b".data\0\0\0" + struct.pack("<IIIIIIHHI", len(payload), 0x1000, len(payload), 0x200, 0, 0, 0, 0, 0xC0000040)
    return (dos + coff + opt + sec).ljust(0x200, b"\0") + payload


def main():
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "t.dll"
        exe.write_bytes(tiny_pe(b"hello /wardrobe2 world\0"))
        con = graph.init_db(Path(td) / "g.db")
        probes = [{"name": "w2", "kind": "string", "needle": "wardrobe2"},
                  {"name": "w8", "kind": "string", "needle": "wardrobe8"}]
        for _ in range(2):
            persist_probes(con, str(exe), "snap:t", probes)
        rows = dict(con.execute("select observation_id,status from capability_observations").fetchall())
        assert len(rows) == 2, rows
        assert rows["capability-observation:snap:t:t.dll:w2"] == "VERIFIED", rows
        assert rows["capability-observation:snap:t:t.dll:w8"] == "UNKNOWN", rows
        con.close()
    print("binary probes self-test: PASS")


if __name__ == "__main__":
    main()
