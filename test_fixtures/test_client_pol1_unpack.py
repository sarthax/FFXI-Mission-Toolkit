#!/usr/bin/env python3
"""Self-test for bounded read-only POL1 unpacker."""
import struct
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.pol1_unpack import unpack_pol1, search_unpacked, Pol1Error


def make_pe(packed, expected):
    pe = 0x80
    image = bytearray(0x200 + len(packed))
    image[0x3c:0x40] = struct.pack("<I", pe)
    image[pe:pe+4] = b"PE\0\0"
    struct.pack_into("<H", image, pe+6, 2)
    struct.pack_into("<H", image, pe+20, 0xe0)
    table = pe+24+0xe0
    for off, name, vsize, rva, raw_size, raw_off in (
        (table, b".text", expected, 0x1000, 0, 0),
        (table+40, b"POL1", len(packed), 0x9000, len(packed), 0x200)):
        image[off:off+8] = name.ljust(8, b"\0")
        struct.pack_into("<IIII", image, off+8, vsize, rva, raw_size, raw_off)
    image[0x200:] = packed
    return bytes(image)


def main():
    # literals "abc" then three-byte backreference for "abc"
    packed = b"\xe0abc\x00\x03"
    out = unpack_pol1(make_pe(packed, 6))
    assert out["bytes"] == b"abcabc", out
    assert out["base_rva"] == 0x1000
    for bad in (b"", make_pe(packed, 7), make_pe(b"\x00\x00\x01", 3)):
        try:
            unpack_pol1(bad)
        except Pol1Error:
            pass
        else:
            raise AssertionError("corrupt input accepted")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "sample.dll"
        path.write_bytes(make_pe(packed, 6))
        found = search_unpacked(path, "61 62 63")
        assert [hit["rva"] for hit in found["hits"]] == [0x1000, 0x1003]
        assert found["unpacked_sha256"] == out["sha256"]
        assert search_unpacked(path, "ff")["status"] == "UNKNOWN"
        for invalid in ("", "GG", "aa ?", "aa " * 65):
            try:
                search_unpacked(path, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid pattern accepted: {invalid!r}")
    print("POL1 unpack self-test: PASS")


if __name__ == "__main__":
    main()
