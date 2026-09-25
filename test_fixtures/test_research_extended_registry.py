#!/usr/bin/env python3
import gzip
import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Capability, Evidence
from workbench.research import (
    CaptureResearchReader, ClientResearchReader, ReferenceResearchReader,
    ResearchSessionStore,
)
from workbench.research.tools import ResearchToolRegistry, register_extended_tools


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)

        capture_db=root/"captures.db"
        con=sqlite3.connect(capture_db)
        con.execute("CREATE TABLE captures(capture_id INTEGER PRIMARY KEY,source_path TEXT,capturer TEXT,capture_label TEXT,content_type TEXT,zones TEXT,mission_name TEXT,addons TEXT,client_build TEXT,is_retail INTEGER,start_time INTEGER,ingested_at TEXT)")
        con.execute("INSERT INTO captures VALUES(1,'cap.zip','tester','Ilrusi','Assault','Ilrusi Atoll','Golden Salvage','PacketLogger','30191204_1',1,0,'now')")
        con.commit(); con.close()

        dump=root/"wiki.jsonl.gz"
        with gzip.open(dump,"wt",encoding="utf-8") as f:
            f.write(json.dumps({
                "title":"Ancient Vows","pageid":1,"revid":2,"timestamp":"2026-01-01",
                "url":"https://example.invalid","categories":["Missions"],"wikitext":"Mammet battlefield",
            })+"\n")

        db=root/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Evidence(
            "evidence:client","CLIENT_SOURCE","fixture","client","client:test","client"
        ))
        graph.insert_record(con,Capability(
            "cap:wardrobe","wardrobe_slots","CLIENT","client:test","client:test",
            "VERIFIED",4,"evidence:client"
        ))
        con.commit(); con.close()

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:extended",
            question="Inspect client and reference evidence.",
            provider="fixture",
            model="fixture",
        )

        registry=ResearchToolRegistry()
        register_extended_tools(
            registry,
            capture_reader=CaptureResearchReader(capture_db,db),
            reference_reader=ReferenceResearchReader(dump),
            client_reader=ClientResearchReader(db),
        )

        cap=registry.call(
            "client.capability",
            {"name":"wardrobe"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert cap["evidence_ids"]==["evidence:client"],cap

        ref=registry.call(
            "reference.search",
            {"query":"Mammet"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert ref["matches"][0]["authority"]=="REFERENCE",ref

        capture=registry.call(
            "capture.search",
            {"query":"Ilrusi"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert capture["matches"][0]["capture_id"]==1,capture

        loaded=store.get(session.research_session_id)
        assert len(loaded["tool_calls"])==3,loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:client"],loaded

        specs={row["name"]:row for row in registry.specs()}
        for name in (
            "capture.search","capture.backtrace",
            "reference.search","reference.compare",
            "client.capability","dat.lookup",
        ):
            assert specs[name]["access"]=="READ",specs

    print("capture reference client registry self-test: PASS")


if __name__=="__main__":
    main()
