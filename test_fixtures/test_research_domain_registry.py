#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Binding, Evidence, Function
from workbench.research import ResearchSessionStore, WorkbenchDomainReader
from workbench.research.tools import ResearchToolRegistry, register_domain_tools


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Evidence(
            "evidence:binding","SERVER_SOURCE","fixture","lua.cpp:10","src","binding"
        ))
        graph.insert_record(con,Function(
            "fn:getID","CLuaBaseEntity::getID","getID",
            class_name="CLuaBaseEntity",source_snapshot_id="src",
            path="lua.cpp",line=20,definition=True
        ))
        graph.insert_record(con,Binding(
            "binding:getID","getID","LUNAR","CLuaBaseEntity::getID",
            "CLuaBaseEntity","fn:getID","src","lua.cpp",10,
            "evidence:binding","RESOLVED"
        ))
        con.commit()
        con.close()

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:domain",
            question="Resolve getID binding.",
            provider="fixture",
            model="fixture",
        )

        registry=ResearchToolRegistry()
        register_domain_tools(registry,WorkbenchDomainReader(db))

        result=registry.call(
            "binding.lookup",
            {"lua_name":"getID","class_name":"CLuaBaseEntity"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert result["status"]=="OK",result
        assert result["matches"][0]["binding_id"]=="binding:getID",result
        assert result["evidence_ids"]==["evidence:binding"],result

        loaded=store.get(session.research_session_id)
        assert loaded["tool_calls"][0]["tool_name"]=="binding.lookup",loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:binding"],loaded

        specs={row["name"]:row for row in registry.specs()}
        for name in (
            "feature.inspect","entity.lookup","binding.lookup",
            "packet.lookup","validation.inspect",
            "server.symbol","server.enum","server.build-target",
        ):
            assert specs[name]["access"]=="READ",specs

    print("typed domain research registry self-test: PASS")


if __name__=="__main__":
    main()
