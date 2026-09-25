#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.research import ResearchSessionStore
from workbench.research.client_binary_tools import ClientBinaryResearchReader
from workbench.research.tools import ResearchToolRegistry, register_client_binary_tools


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        index=root/"binary.json"
        index.write_text(json.dumps({
            "schema":1,
            "kind":"CLIENT_BINARY_INDEX",
            "binary":{
                "label":"FFXiMain.dll","filename":"FFXiMain.dll","path":"FFXiMain.dll",
                "sha256":"a"*64,"client_build":"fixture","image_base":0x400000,
            },
            "sections":[{"name":".text","virtual_address":0x1000,"virtual_size":0x100,"raw_offset":0x200,"raw_size":0x100,"characteristics":0}],
            "imports":[{"dll":"KERNEL32.dll","name":"CreateFileA","ordinal":None,"hint":0,"thunk_rva":0x2000}],
            "exports":[],
            "strings":[{"encoding":"ascii","text":"/wardrobe4","offset":0x220,"rva":0x1020,"va":0x401020,"section":".text"}],
            "analysis":{"authority":"CLIENT_BINARY","status":"INDEXED"},
        }),encoding="utf-8")
        index2=root/"binary2.json"
        index2.write_text(json.dumps({
            "schema":1,
            "kind":"CLIENT_BINARY_INDEX",
            "binary":{
                "label":"FFXiMain-new.dll","filename":"FFXiMain-new.dll","path":"FFXiMain-new.dll",
                "sha256":"b"*64,"client_build":"fixture-new","image_base":0x400000,
                "file_size":2048,
            },
            "sections":[{"name":".text","virtual_address":0x1000,"virtual_size":0x120,"raw_offset":0x200,"raw_size":0x200,"characteristics":0}],
            "imports":[
                {"dll":"KERNEL32.dll","name":"CreateFileA","ordinal":None,"hint":0,"thunk_rva":0x2000},
                {"dll":"USER32.dll","name":"MessageBoxA","ordinal":None,"hint":0,"thunk_rva":0x2010}
            ],
            "exports":[],
            "strings":[
                {"encoding":"ascii","text":"/wardrobe4","offset":0x220,"rva":0x1020,"va":0x401020,"section":".text"},
                {"encoding":"ascii","text":"/wardrobe5","offset":0x240,"rva":0x1040,"va":0x401040,"section":".text"}
            ],
            "analysis":{"authority":"CLIENT_BINARY","status":"INDEXED"},
        }),encoding="utf-8")

        store=ResearchSessionStore(root/"workbench.db")
        session=store.create(
            research_session_id="research:binary",
            question="Inspect client binary evidence.",
            provider="fixture",
            model="fixture",
        )
        registry=ResearchToolRegistry()
        register_client_binary_tools(registry,ClientBinaryResearchReader([index,index2]))

        result=registry.call(
            "client.string-search",
            {"query":"wardrobe"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert result["status"]=="OK",result
        assert result["matches"][0]["authority"]=="CLIENT_BINARY",result

        info=registry.call(
            "client.binary-info",
            {"query":"FFXiMain"},
            permission_profile="READ_ONLY_RESEARCH",
        )
        assert info["matches"][0]["sha256"]=="a"*64,info

        diff=registry.call(
            "client.binary-diff",
            {"left":"FFXiMain.dll","right":"FFXiMain-new.dll"},
            permission_profile="READ_ONLY_RESEARCH",
        )
        assert diff["status"]=="DIFFERENT",diff
        assert diff["imports"]["added_count"]==1,diff
        assert diff["strings"]["added_count"]==1,diff

        specs={row["name"]:row for row in registry.specs()}
        for name in (
            "client.binary-info","client.sections","client.imports","client.exports",
            "client.string-search","client.address-evidence","client.binary-diff",
        ):
            assert specs[name]["access"]=="READ",specs

        loaded=store.get(session.research_session_id)
        assert loaded["tool_calls"][0]["tool_name"]=="client.string-search",loaded

    print("client binary research registry self-test: PASS")


if __name__=="__main__":
    main()
