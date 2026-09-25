#!/usr/bin/env python3
import gzip
import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

import workbench.research.extended_tools as ext
from workbench.core import graph
from workbench.core.schema import Capability, Evidence
from workbench.research.extended_tools import CaptureResearchReader, ReferenceResearchReader, ClientResearchReader


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)

        capture_db=root/"captures.db"
        con=sqlite3.connect(capture_db)
        con.execute("CREATE TABLE captures(capture_id INTEGER PRIMARY KEY,source_path TEXT,capturer TEXT,capture_label TEXT,content_type TEXT,zones TEXT,mission_name TEXT,addons TEXT,client_build TEXT,is_retail INTEGER,start_time INTEGER,ingested_at TEXT)")
        con.execute("INSERT INTO captures VALUES(1,'cap.zip','tester','Ilrusi capture','Assault','Ilrusi Atoll','Golden Salvage','PacketLogger','30191204_1',1,0,'now')")
        con.commit(); con.close()
        captures=CaptureResearchReader(capture_db)
        found=captures.search("Ilrusi")
        assert found["matches"][0]["capture_id"]==1,found
        assert found["authority"]=="CAPTURE_RUNTIME_OBSERVATION",found

        dump=root/"wiki.jsonl.gz"
        with gzip.open(dump,"wt",encoding="utf-8") as f:
            f.write(json.dumps({"title":"Ancient Vows","pageid":1,"revid":2,"timestamp":"2026-01-01","url":"https://example.invalid","categories":["Missions"],"wikitext":"Mammet battlefield"})+"\n")
        ref=ReferenceResearchReader(dump)
        search=ref.search("Mammet")
        assert search["matches"][0]["title"]=="Ancient Vows",search
        assert search["matches"][0]["authority"]=="REFERENCE",search
        compare=ref.compare(["Ancient Vows","Missing"])
        assert compare["missing"]==["Missing"],compare

        graph_db=root/"workbench.db"
        con=graph.init_db(graph_db)
        graph.insert_record(con,Evidence("evidence:client","CLIENT_SOURCE","fixture","client","client:test","client"))
        graph.insert_record(con,Capability("cap:wardrobe","wardrobe_slots","CLIENT","client:test","client:test","VERIFIED",4,"evidence:client"))
        con.commit(); con.close()
        client=ClientResearchReader(graph_db)
        cap=client.capability("wardrobe")
        assert cap["matches"][0]["value"]==4,cap
        assert cap["evidence_ids"]==["evidence:client"],cap

        original_read=ext.item_dat_tools.read_client_item
        original_dict=ext.item_dat_tools.item_to_dict
        original_detect=ext.item_dat_tools.detect_stride_path
        try:
            ext.item_dat_tools.read_client_item=lambda item_id: SimpleNamespace(
                id=item_id,dat="ROM/0/1.DAT",dat_ui="ROM/0/1.DAT",format="legacy",
                record_index=5,
            )
            ext.item_dat_tools.item_to_dict=lambda rec:{"id":rec.id,"name":"Test Sword","level":90}
            ext.item_dat_tools.detect_stride_path=lambda path:0xC00
            dat=client.dat_lookup(1234)
            assert dat["status"]=="OK",dat
            assert dat["item"]["level"]==90,dat
            assert dat["authority"]=="CLIENT_DAT",dat
        finally:
            ext.item_dat_tools.read_client_item=original_read
            ext.item_dat_tools.item_to_dict=original_dict
            ext.item_dat_tools.detect_stride_path=original_detect

    print("capture reference client research readers self-test: PASS")


if __name__=="__main__":
    main()
