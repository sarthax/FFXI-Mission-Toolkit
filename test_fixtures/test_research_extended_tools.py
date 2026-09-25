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
        con.execute("CREATE TABLE capture_raw_packets(capture_id INTEGER, seq INTEGER, direction TEXT, opcode TEXT, raw TEXT)")
        con.execute("INSERT INTO captures VALUES(1,'cap.zip','tester','Ilrusi capture','Assault','Ilrusi Atoll','Golden Salvage','PacketLogger','30191204_1',1,0,'now')")
        con.execute("INSERT INTO capture_raw_packets VALUES(1,1,'incoming','0x02A','00')")
        con.commit(); con.close()
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
        con.execute(
            "INSERT INTO entity_relationships(relationship_id,source_node,target_node,relationship,evidence_id,confidence,status,metadata_json,source_snapshot_id) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("edge:packet","packet:0x02A","function:packet","HANDLED_BY","evidence:client","VERIFIED","DISCOVERED","{}","src"),
        )
        con.commit(); con.close()
        captures=CaptureResearchReader(capture_db,graph_db)
        found=captures.search("Ilrusi")
        assert found["matches"][0]["capture_id"]==1,found
        assert found["authority"]=="CAPTURE_RUNTIME_OBSERVATION",found
        traced=captures.backtrace(1)
        assert traced["status"]=="OK",traced
        packet_checks=[c for c in traced["checks"] if c.get("kind")=="PACKET"]
        assert packet_checks and packet_checks[0]["canonical_packet_node"]=="packet:0x02A",traced

        client=ClientResearchReader(graph_db)
        cap=client.capability("wardrobe")
        assert cap["matches"][0]["value"]==4,cap
        assert cap["evidence_ids"]==["evidence:client"],cap

        original_read=ext.item_dat_tools.read_client_item
        original_dict=ext.item_dat_tools.item_to_dict
        original_detect=ext.item_dat_tools.detect_stride_path
        original_category=ext.item_dat_tools.category_for_item
        original_path=ext.item_dat_tools.dat_path
        original_count=ext.item_dat_tools.record_count
        original_layout=ext.item_dat_tools.layout_for_type
        original_format=ext.item_dat_tools.format_for_stride
        original_describe=ext.item_dat_tools.describe
        try:
            ext.item_dat_tools.read_client_item=lambda item_id: SimpleNamespace(
                id=item_id,dat="ROM/0/1.DAT",dat_ui="ROM/0/1.DAT",format="legacy",
                record_index=5,
            )
            ext.item_dat_tools.item_to_dict=lambda rec:{"id":rec.id,"name":"Test Sword","level":90}
            fake_dat=root/"fake.DAT"
            fake_dat.write_bytes(b"x")
            ext.item_dat_tools.detect_stride_path=lambda path:0xC00
            ext.item_dat_tools.category_for_item=lambda item_id:("weapons",1000,4,"ROM/0/1.DAT","ROM/0/2.DAT")
            ext.item_dat_tools.dat_path=lambda rom:fake_dat
            ext.item_dat_tools.record_count=lambda path:100
            ext.item_dat_tools.layout_for_type=lambda item_type:"weapon"
            ext.item_dat_tools.format_for_stride=lambda stride:"legacy"
            ext.item_dat_tools.describe=lambda stride:"legacy test layout"

            described=client.dat_describe(item_id=1234)
            assert described["status"]=="OK",described
            assert described["record_count"]==100,described
            assert described["layout"]=="weapon",described

            dat=client.dat_lookup(1234)
            assert dat["status"]=="OK",dat
            assert dat["item"]["level"]==90,dat
            assert dat["authority"]=="CLIENT_DAT",dat
        finally:
            ext.item_dat_tools.read_client_item=original_read
            ext.item_dat_tools.item_to_dict=original_dict
            ext.item_dat_tools.detect_stride_path=original_detect
            ext.item_dat_tools.category_for_item=original_category
            ext.item_dat_tools.dat_path=original_path
            ext.item_dat_tools.record_count=original_count
            ext.item_dat_tools.layout_for_type=original_layout
            ext.item_dat_tools.format_for_stride=original_format
            ext.item_dat_tools.describe=original_describe

    print("capture reference client research readers self-test: PASS")


if __name__=="__main__":
    main()
