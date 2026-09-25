#!/usr/bin/env python3
import json
import sqlite3
import struct
import tempfile
from pathlib import Path

from workbench.client.binary_index import PEImage, index_binary, write_index
from workbench.core.services.client_binary_graph import ingest_client_binary_index
from workbench.research.client_binary_tools import ClientBinaryResearchReader


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
    struct.pack_into("<I",data,opt+20,0x1000)
    struct.pack_into("<I",data,opt+24,0x2000)
    struct.pack_into("<I",data,opt+28,0x400000)
    struct.pack_into("<I",data,opt+32,0x1000)
    struct.pack_into("<I",data,opt+36,0x200)
    struct.pack_into("<I",data,opt+56,0x3000)
    struct.pack_into("<I",data,opt+60,0x200)
    struct.pack_into("<H",data,opt+68,2)
    struct.pack_into("<I",data,opt+92,16)
    struct.pack_into("<II",data,opt+96,0x2100,0x80)
    struct.pack_into("<II",data,opt+104,0x2200,0x80)

    sec=opt+0xE0
    data[sec:sec+8]=b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI",data,sec+8,0x180,0x1000,0x200,0x200,0,0,0,0,0x60000020)
    sec2=sec+40
    data[sec2:sec2+8]=b".rdata\0\0"
    struct.pack_into("<IIIIIIHHI",data,sec2+8,0x400,0x2000,0x400,0x400,0,0,0,0,0x40000040)

    data[0x220:0x22E]=b"WARDROBE_TEST\0"
    wide="WideString".encode("utf-16le")+b"\0\0"
    data[0x240:0x240+len(wide)]=wide

    export_off=0x500
    struct.pack_into(
        "<IIHHIIIIIII",data,export_off,
        0,0,0,0,0x2140,1,1,1,0x2150,0x2154,0x2158,
    )
    data[0x540:0x54D]=b"Fixture.dll\0"
    struct.pack_into("<I",data,0x550,0x1010)
    struct.pack_into("<I",data,0x554,0x2160)
    struct.pack_into("<H",data,0x558,0)
    data[0x560:0x56B]=b"TestExport\0"

    struct.pack_into("<IIIII",data,0x600,0x2240,0,0,0x2280,0x2260)
    struct.pack_into("<I",data,0x640,0x2290)
    struct.pack_into("<I",data,0x644,0)
    struct.pack_into("<I",data,0x660,0x2290)
    struct.pack_into("<I",data,0x664,0)
    data[0x680:0x68D]=b"KERNEL32.dll\0"
    struct.pack_into("<H",data,0x690,0)
    data[0x692:0x69E]=b"CreateFileA\0"

    path.write_bytes(data)


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        binary=root/"fixture.dll"
        build_fixture(binary)

        image=PEImage(binary)
        assert image.pe_kind=="PE32"
        assert image.image_base==0x400000
        assert image.rva_to_offset(0x1020)==0x220
        assert image.offset_to_rva(0x220)==0x1020

        imports=image.imports()
        assert any(row["dll"]=="KERNEL32.dll" and row["name"]=="CreateFileA" for row in imports),imports
        exports=image.exports()
        assert exports==[{"name":"TestExport","ordinal":1,"rva":0x1010,"va":0x401010}],exports

        payload=index_binary(binary,label="fixture",client_build="fixture-build")
        assert payload["binary"]["sha256"],payload
        assert len(payload["sections"])==2,payload
        assert any(row["text"]=="WARDROBE_TEST" for row in payload["strings"]),payload["strings"]
        assert any(row["encoding"]=="utf-16le" and row["text"]=="WideString" for row in payload["strings"]),payload["strings"]

        index_path=root/"fixture.index.json"
        write_index(payload,index_path)
        graph_db=root/"workbench.db"
        ingested=ingest_client_binary_index(payload,graph_db,source_snapshot_id="client:fixture")
        assert ingested["status"]=="OK",ingested

        con=sqlite3.connect(graph_db)
        artifact=con.execute(
            "SELECT artifact_type,source_snapshot_id FROM artifacts WHERE artifact_id=?",
            (ingested["artifact_id"],),
        ).fetchone()
        assert artifact==("CLIENT_BINARY","client:fixture"),artifact
        assert con.execute(
            "SELECT COUNT(*) FROM findings WHERE analysis_id=?",
            (ingested["analysis_id"],),
        ).fetchone()[0] >= 13
        con.close()

        reader=ClientBinaryResearchReader([index_path])
        info=reader.binary_info("fixture")
        assert info["matches"][0]["client_build"]=="fixture-build",info
        strings=reader.string_search("WARDROBE")
        assert strings["matches"][0]["rva"]==0x1020,strings
        imp=reader.imports("fixture",query="CreateFile")
        assert imp["imports"][0]["dll"]=="KERNEL32.dll",imp
        exp=reader.exports("fixture",query="TestExport")
        assert exp["exports"][0]["ordinal"]==1,exp
        addr=reader.address_evidence("fixture",rva=0x1020)
        assert addr["offset"]==0x220,addr
        assert addr["section"]["name"]==".text",addr

    print("client binary indexing pipeline self-test: PASS")


if __name__=="__main__":
    main()
