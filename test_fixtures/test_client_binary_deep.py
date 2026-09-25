#!/usr/bin/env python3
import struct
import tempfile
from pathlib import Path

from workbench.client.binary_deep import byte_search, function_candidates, parse_hex_pattern, xrefs


def build_fixture(path: Path) -> None:
    data=bytearray(0x800)
    data[0:2]=b"MZ"
    struct.pack_into("<I",data,0x3C,0x80)
    data[0x80:0x84]=b"PE\0\0"
    coff=0x84
    struct.pack_into("<HHIIIHH",data,coff,0x14C,2,0x12345678,0,0,0xE0,0x010F)
    opt=coff+20
    struct.pack_into("<H",data,opt,0x10B)
    struct.pack_into("<I",data,opt+16,0x1000)
    struct.pack_into("<I",data,opt+28,0x400000)
    struct.pack_into("<I",data,opt+32,0x1000)
    struct.pack_into("<I",data,opt+36,0x200)
    struct.pack_into("<I",data,opt+56,0x3000)
    struct.pack_into("<I",data,opt+60,0x200)
    struct.pack_into("<H",data,opt+68,2)
    struct.pack_into("<I",data,opt+92,16)
    sec=opt+0xE0
    data[sec:sec+8]=b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI",data,sec+8,0x200,0x1000,0x200,0x200,0,0,0,0,0x60000020)
    sec2=sec+40
    data[sec2:sec2+8]=b".rdata\0\0"
    struct.pack_into("<IIIIIIHHI",data,sec2+8,0x200,0x2000,0x200,0x400,0,0,0,0,0x40000040)

    # 0x1010 calls 0x1050; a literal VA pointer to 0x1050 lives in .rdata.
    source_rva=0x1010
    target_rva=0x1050
    disp=target_rva-(source_rva+5)
    data[0x210]=0xE8
    struct.pack_into("<i",data,0x211,disp)
    data[0x215:0x219]=bytes.fromhex("83 C4 04 C3")
    data[0x250:0x254]=bytes.fromhex("55 8B EC C3")
    struct.pack_into("<I",data,0x420,0x400000+target_rva)
    path.write_bytes(data)


def main():
    assert parse_hex_pattern("E8 ?? ?? ?? ??")== (0xE8,None,None,None,None)
    with tempfile.TemporaryDirectory() as td:
        binary=Path(td)/"fixture.dll"
        build_fixture(binary)

        pat=byte_search(binary,"E8 ?? ?? ?? ?? 83 C4 04",executable_only=True)
        assert len(pat["matches"])==1,pat
        assert pat["matches"][0]["rva"]==0x1010,pat

        refs=xrefs(binary,rva=0x1050)
        kinds={row["kind"] for row in refs["xrefs"]}
        assert "CALL_REL32" in kinds,refs
        assert "ABSOLUTE_VA32" in kinds,refs

        funcs=function_candidates(binary)
        by_rva={row["rva"]:row for row in funcs["candidates"]}
        assert 0x1000 in by_rva,funcs
        assert by_rva[0x1000]["confidence"]=="VERIFIED_SEED",funcs
        assert 0x1050 in by_rva,funcs
        assert any(reason.startswith("DIRECT_CALL_FROM") for reason in by_rva[0x1050]["reasons"]),funcs

    print("client binary deep analysis self-test: PASS")


if __name__=="__main__":
    main()
