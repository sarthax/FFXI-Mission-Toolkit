#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import (
    Binding, BuildTarget, DependencyEdge, EnumDefinition, Evidence,
    Feature, Finding, Function, ValidationResult, ValidationRun,
)
from workbench.research.domain_tools import WorkbenchDomainReader


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Feature(
            "feature:test","Ancient Vows","MISSION","cop","src","dst"
        ))
        graph.insert_record(con,Evidence(
            "evidence:feature","SERVER_SOURCE","fixture","mission.lua:1","src","feature"
        ))
        graph.insert_record(con,Evidence(
            "evidence:function","SERVER_SOURCE","fixture","packet.cpp:20","src","function"
        ))
        graph.insert_record(con,Evidence(
            "evidence:binding","SERVER_SOURCE","fixture","lua.cpp:10","src","binding"
        ))
        graph.insert_record(con,Function(
            "fn:packet","SmallPacket0x02A","SmallPacket0x02A",
            source_snapshot_id="src",path="packet.cpp",line=20,definition=True,
            evidence_id="evidence:function",
        ))
        graph.insert_record(con,Binding(
            "binding:getID","getID","LUNAR","CLuaBaseEntity::getID",
            "CLuaBaseEntity","fn:packet","src","lua.cpp",10,
            "evidence:binding","RESOLVED"
        ))
        con.execute(
            "INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            ("entity:test","NPC","Test NPC",'{"zone_id":31}'),
        )
        con.execute(
            "INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) "
            "VALUES(?,?,?,?)",
            ("entity:test","npcid","17000001","src"),
        )
        graph.insert_record(con,Finding(
            "finding:test","analysis:test","entity:test","name","Test NPC",
            "VERIFIED","VERIFIED","evidence:feature","src"
        ))
        graph.insert_record(con,EnumDefinition(
            "enum:state:ready","PacketState","src","packet.h",5,
            "CXX_ENUM","1","READY","evidence:function"
        ))
        graph.insert_record(con,BuildTarget(
            "build-target:map","map","CMAKE","src/map/CMakeLists.txt",
            "src",None,"DISCOVERED"
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:packet","packet:0x02A","fn:packet","HANDLED_BY",
            "evidence:feature","VERIFIED","DISCOVERED",{}, "src"
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:enum","fn:packet","enum:state:ready","USES_ENUM",
            "evidence:function","INFERRED","DISCOVERED",{}, "src"
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:build","fn:packet","build-target:map","BUILDS_INTO",
            "evidence:function","VERIFIED","DISCOVERED",{}, "src"
        ))
        con.execute(
            "INSERT INTO capabilities(capability_id,name,capability_type,subject_id,source_snapshot_id,status,value_json,evidence_id,notes_json) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("cap:test","battlefield_support","SERVER","feature:test","src","VERIFIED","true","evidence:feature","[]"),
        )
        con.execute(
            "INSERT INTO capability_observations(observation_id,capability_id,source_snapshot_id,status,value_json,evidence_id,notes_json) "
            "VALUES(?,?,?,?,?,?,?)",
            ("obs:test","cap:test","dst","VERIFIED","true","evidence:feature","[]"),
        )
        con.execute(
            "INSERT INTO capability_requirements(requirement_id,feature_id,capability_id,required,status,evidence_id,notes_json) "
            "VALUES(?,?,?,?,?,?,?)",
            ("req:test","feature:test","cap:test",1,"VERIFIED","evidence:feature","[]"),
        )
        con.execute(
            "INSERT INTO migrations(migration_id,feature_id,source_snapshot_id,target_snapshot_id,status,metadata_json) "
            "VALUES(?,?,?,?,?,?)",
            ("migration:test","feature:test","src","dst","MANUAL_REQUIRED",'{"reason":"fixture"}'),
        )
        con.execute(
            "INSERT INTO migration_actions(action_id,migration_id,action,artifact_id,status,reason,metadata_json) "
            "VALUES(?,?,?,?,?,?,?)",
            ("action:test","migration:test","MANUAL_REVIEW",None,"MANUAL_REQUIRED","fixture",'{}'),
        )
        graph.insert_record(con,ValidationRun(
            "run:test","test run","src","dst","feature:test","VERIFIED"
        ))
        graph.insert_record(con,ValidationResult(
            "validation:test","LUA_SANITY","feature:test","VERIFIED",
            "evidence:feature","src","dst",run_id="run:test"
        ))
        con.commit()
        con.close()

        reader=WorkbenchDomainReader(db)

        feature=reader.feature_inspect("feature:test")
        assert feature["feature"]["feature_id"]=="feature:test",feature

        entity=reader.entity_lookup("17000001",identifier_type="npcid")
        assert entity["matches"][0]["entity_id"]=="entity:test",entity
        assert "evidence:feature" in entity["evidence_ids"],entity

        binding=reader.binding_lookup("getID",class_name="CLuaBaseEntity")
        assert binding["matches"][0]["binding_id"]=="binding:getID",binding
        assert "evidence:binding" in binding["evidence_ids"],binding

        packet=reader.packet_lookup("0x02A")
        assert packet["relationships"][0]["relationship"]=="HANDLED_BY",packet
        assert "evidence:feature" in packet["evidence_ids"],packet

        validation=reader.validation_inspect(feature_id="feature:test")
        assert validation["runs"][0]["run_id"]=="run:test",validation
        assert validation["results"][0]["status"]=="VERIFIED",validation
        assert validation["evidence_ids"]==["evidence:feature"],validation

        symbol=reader.server_symbol_lookup("SmallPacket0x02A")
        assert symbol["matches"][0]["function_id"]=="fn:packet",symbol
        assert any(edge["relationship"]=="USES_ENUM" for edge in symbol["matches"][0]["relationships"]),symbol
        assert "evidence:function" in symbol["evidence_ids"],symbol

        enum=reader.server_enum_lookup("READY",enum_name="PacketState")
        assert enum["matches"][0]["enum_id"]=="enum:state:ready",enum
        assert enum["matches"][0]["usage"][0]["source_node"]=="fn:packet",enum

        build=reader.server_build_target_lookup("map")
        assert build["matches"][0]["target_id"]=="build-target:map",build
        assert any(edge["relationship"]=="BUILDS_INTO" for edge in build["matches"][0]["relationships"]),build

        capability=reader.capability_inspect("battlefield_support",feature_id="feature:test")
        assert capability["matches"][0]["capability_id"]=="cap:test",capability
        assert capability["matches"][0]["observations"][0]["status"]=="VERIFIED",capability
        assert capability["matches"][0]["requirements"][0]["required"] is True,capability
        assert "evidence:feature" in capability["evidence_ids"],capability

        migration=reader.migration_inspect("migration:test")
        assert migration["matches"][0]["migration_id"]=="migration:test",migration
        assert migration["matches"][0]["actions"][0]["action"]=="MANUAL_REVIEW",migration

    print("typed domain research tools self-test: PASS")


if __name__=="__main__":
    main()
