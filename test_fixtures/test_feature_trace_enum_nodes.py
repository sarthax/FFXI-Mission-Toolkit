#!/usr/bin/env python3
"""Regression checks that enum/constant definitions are visible to Feature Trace."""
import tempfile
from pathlib import Path
from workbench.core import graph
from workbench_schema import EnumDefinition
from feature_trace import node_info,search_nodes

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,EnumDefinition("enum:state:READY","State",None,"state.h",1,"CXX_ENUM","1","READY"))
        info=node_info(con,"enum:state:READY")
        assert info["known"],info
        assert any(x["table"]=="enum_definitions" for x in info["representations"]),info
        hits=search_nodes(con,"READY")
        assert any(x["node_id"]=="enum:state:READY" for x in hits),hits
        con.close()
    print("feature trace enum node self-test: PASS")
if __name__=="__main__":
    main()
