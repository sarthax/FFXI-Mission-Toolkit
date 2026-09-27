#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Evidence, Feature, Function
from workbench.research.graph_tools import CanonicalGraphReader


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Feature(
            "feature:test","Ancient Vows","MISSION","cop","src","dst"
        ))
        graph.insert_record(con,Function(
            "fn:test","SmallPacket0x02A","SmallPacket0x02A",
            source_snapshot_id="src",path="packet.cpp",line=10,definition=True
        ))
        graph.insert_record(con,Evidence(
            "evidence:test","SERVER_SOURCE","fixture","packet.cpp:20","src","dispatch"
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:test","feature:test","fn:test","IMPLEMENTED_BY",
            evidence_id="evidence:test",confidence="VERIFIED",
            source_snapshot_id="src"
        ))
        con.commit()
        con.close()

        reader=CanonicalGraphReader(db)
        search=reader.search("Ancient")
        assert search["status"]=="OK",search
        assert search["matches"][0]["node_id"]=="feature:test",search

        trace=reader.trace("feature:test",depth=2)
        assert trace["status"]=="OK",trace
        assert trace["edges"][0]["target_node"]=="fn:test",trace
        assert trace["edges"][0]["confidence"]=="VERIFIED",trace
        assert trace["evidence_ids"]==["evidence:test"],trace
        assert trace["evidence"][0]["location"]=="packet.cpp:20",trace

        bad=reader.trace("feature:test",depth=99)
        assert bad["status"]=="ERROR",bad

    print("canonical graph research tools self-test: PASS")


if __name__=="__main__":
    main()
