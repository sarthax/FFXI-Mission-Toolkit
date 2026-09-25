#!/usr/bin/env python3
"""Regression checks for semantic record-to-graph mirroring."""
from __future__ import annotations
import tempfile
from pathlib import Path
from workbench.core import graph
from workbench_schema import Feature,CapabilityRequirement,Implementation

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,Feature("feature:test","Test","MISSION","Test"))
        graph.insert_record(con,CapabilityRequirement("req:test","feature:test","cap:test",True,"VERIFIED","ev:req"))
        graph.insert_record(con,Implementation("impl:test","feature:test","snap",None,"artifact:test","CPP","VERIFIED",evidence_id="ev:impl"))
        req=con.execute("SELECT target_node,relationship,evidence_id FROM entity_relationships WHERE relationship_id='requires:req:test'").fetchone()
        impl=con.execute("SELECT target_node,relationship,evidence_id,confidence FROM entity_relationships WHERE relationship_id='implements:impl:test'").fetchone()
        assert req==("cap:test","REQUIRES","ev:req"),req
        assert impl==("artifact:test","IMPLEMENTED_BY","ev:impl","VERIFIED"),impl
        con.close()
    print("semantic graph mirror self-test: PASS")
if __name__=="__main__": main()
