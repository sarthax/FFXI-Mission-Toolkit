#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import (
    Binding, DependencyEdge, Entity, Evidence, Feature, Finding, Function,
    ValidationResult, ValidationRun,
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
        graph.insert_record(con,Entity(
            "entity:test","NPC","Test NPC",{"zone_id":31}
        ))
        con.execute(
            "INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) "
            "VALUES(?,?,?,?)",
            ("entity:test","npcid","17000001","src"),
        )
        graph.insert_record(con,Finding(
            "finding:test","analysis:test","entity:test","name","Test NPC",
            "VERIFIED","VERIFIED","evidence:feature","src"
        ))
        graph.insert_record(con,DependencyEdge(
            "edge:packet","packet:0x02A","fn:packet","HANDLED_BY",
            "evidence:feature","VERIFIED","DISCOVERED",{}, "src"
        ))
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

    print("typed domain research tools self-test: PASS")


if __name__=="__main__":
    main()
