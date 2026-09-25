#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Evidence, Feature, Function
from workbench.research import ResearchSessionStore
from workbench.research.graph_tools import CanonicalGraphReader
from workbench.research.tools import ResearchToolRegistry, register_graph_tools


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        db=root/"workbench.db"
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

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:graph-tools",
            question="Trace Ancient Vows",
            provider="fixture",
            model="fixture",
        )
        registry=ResearchToolRegistry()
        register_graph_tools(registry,CanonicalGraphReader(db))

        result=registry.call(
            "graph.trace",
            {"root":"feature:test","depth":2},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert result["status"]=="OK",result
        assert result["evidence_ids"]==["evidence:test"],result

        loaded=store.get(session.research_session_id)
        assert len(loaded["tool_calls"])==1,loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:test"],loaded

        search=registry.call(
            "graph.search",
            {"query":"Ancient"},
            permission_profile="READ_ONLY_RESEARCH",
        )
        assert search["matches"][0]["node_id"]=="feature:test",search

    print("research graph registry integration self-test: PASS")


if __name__=="__main__":
    main()
