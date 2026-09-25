#!/usr/bin/env python3
"""Regression checks for evidence-preserving feature candidate traversal."""
from __future__ import annotations
import sqlite3,tempfile
from pathlib import Path
from workbench.core import graph
from workbench_schema import Feature
from feature_candidates import candidates

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,Feature("feature:test:1","Test Mission","MISSION","Test",status="DISCOVERED"))
        con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                    ("h","packet:0x02a","function:handler","HANDLED_BY","server-handler","VERIFIED","DISCOVERED","{}",None))
        con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                    ("f","feature:test:1","function:handler","IMPLEMENTED_BY","server-feature","VERIFIED","DISCOVERED","{}",None))
        con.commit()
        result=candidates(con,"packet:0x02a",4)
        assert len(result["candidates"])==1,result
        hit=result["candidates"][0]
        assert hit["feature_id"]=="feature:test:1"
        assert hit["distance"]==2
        assert [step["relationship"] for step in hit["path"]]==["HANDLED_BY","IMPLEMENTED_BY"]
        assert [step["evidence_id"] for step in hit["path"]]==["server-handler","server-feature"]
        con.close()
    print("feature candidate traversal self-test: PASS")
if __name__=="__main__": main()
