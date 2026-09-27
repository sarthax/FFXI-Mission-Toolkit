#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Function, Binding, EnumDefinition, BuildTarget, DependencyEdge


def main():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        con=graph.init_db(Path(tmp.name))
        graph.insert_record(con,Function(
            "fn:handler",
            "SmallPacket0x02A",
            "SmallPacket0x02A",
            path="src/map/packet_system.cpp",
            line=100,
            definition=True,
        ))
        graph.insert_record(con,Binding(
            "binding:test",
            "handlePacket",
            "LUNAR",
            "SmallPacket0x02A",
            None,
            "fn:handler",
            status="RESOLVED",
        ))
        graph.insert_record(con,EnumDefinition(
            "enum:state:ready",
            "PacketState",
            None,
            "src/map/packet_system.h",
            10,
            "CXX_ENUM",
            "1",
            "READY",
        ))
        graph.insert_record(con,BuildTarget(
            "build-target:map",
            "map",
            "CMAKE",
            "src/map/CMakeLists.txt",
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:packet-handler",
            "packet:0x02A",
            "cpp-symbol:SmallPacket0x02A",
            "HANDLED_BY",
            confidence="VERIFIED",
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:handler-enum",
            "fn:handler",
            "PacketState::READY",
            "USES_ENUM",
            confidence="INFERRED",
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:handler-build",
            "fn:handler",
            "build-target:map",
            "BUILDS_INTO",
            confidence="VERIFIED",
        ))
        graph.resolve_relationships(con)
        con.commit()

        packet=con.execute(
            "SELECT target_node,confidence FROM entity_relationships WHERE relationship_id='edge:packet-handler'"
        ).fetchone()
        enum=con.execute(
            "SELECT target_node,confidence,metadata_json FROM entity_relationships WHERE relationship_id='edge:handler-enum'"
        ).fetchone()
        binding=con.execute(
            "SELECT target_node,confidence FROM entity_relationships WHERE relationship_id='binds:binding:test:fn:handler'"
        ).fetchone()
        build=con.execute(
            "SELECT target_node,confidence FROM entity_relationships WHERE relationship_id='edge:handler-build'"
        ).fetchone()

        assert packet==("fn:handler","VERIFIED"),packet
        assert binding==("fn:handler","VERIFIED"),binding
        assert enum[0:2]==("enum:state:ready","INFERRED"),enum
        assert json.loads(enum[2])["resolution"]=="exact namespaced enum symbol",enum
        assert build==("build-target:map","VERIFIED"),build
        con.close()

    print("canonical implementation dependency chain self-test: PASS")


if __name__=="__main__":
    main()
