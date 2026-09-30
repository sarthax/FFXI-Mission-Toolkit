#!/usr/bin/env python3
"""Executable regression for Feature Trace Lua -> binding -> engine drill-down."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile

from workbench.core.services.feature_trace_binding_drilldown import (
    binding_index_for_server,
    binding_lookup,
    behavior_engine_drilldown,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        lua=root/"src"/"map"/"lua"
        lua.mkdir(parents=True)
        source=lua/"lua_baseentity.cpp"
        source.write_text(
            """
SOL_REGISTER("getID", CLuaBaseEntity::getID)
SOL_REGISTER("SetPos", CLuaBaseEntity::SetPos)

int32 CLuaBaseEntity::getID(lua_State* L)
{
    return 1;
}

int32 CLuaBaseEntity::SetPos(lua_State* L)
{
    return 0;
}
""".strip()+"\n",
            encoding="utf-8",
        )

        index=binding_index_for_server("topaz",root)
        assert set(index)=={"getID","SetPos"},index

        exact=binding_lookup("topaz",root,"getID",index=index)
        assert exact["status"]=="EXACT",exact
        assert exact["locations"][0]["class"]=="CLuaBaseEntity",exact
        assert exact["locations"][0]["registration_excerpt"],exact
        assert exact["locations"][0]["implementation_line"],exact
        assert "CLuaBaseEntity::getID" in exact["locations"][0]["implementation_excerpt"]["text"],exact

        case=binding_lookup("topaz",root,"setpos",index=index)
        assert case["status"]=="CASE_ONLY",case
        assert case["resolved_name"]=="SetPos",case
        missing=binding_lookup("topaz",root,"doesNotExist",index=index)
        assert missing["status"]=="NOT_INDEXED",missing
        assert missing["locations"]==[],missing

        effect=lambda method,line: SimpleNamespace(
            effect="API_CALL",
            target="player",
            value=method,
            metadata={
                "qualified_name":f"player:{method}",
                "source_line":line,
                "source_line_text":f"player:{method}()",
            },
        )
        rule=SimpleNamespace(
            effects=(effect("getID",3),effect("setpos",4),effect("doesNotExist",5)),
            metadata={"hook":"onTrigger","hook_owner":"entity"},
            trigger="ONTRIGGER",
        )
        behavior=SimpleNamespace(rules=(rule,))
        inspected={
            "behavior":behavior,
            "shared_helpers":[{
                "qualified_name":"xi.demo.helper",
                "status":"RESOLVED",
                "candidates":[{"path":"scripts/globals/demo.lua","line":10}],
                "analysis":{
                    "api_calls":[{
                        "qualified_name":"player:getID",
                        "receiver":"player",
                        "function":"getID",
                        "line":11,
                        "source_line":"player:getID()",
                    }],
                    "shared_helper_callees":[{
                        "qualified_name":"xi.demo.inner",
                        "status":"UNRESOLVED",
                    }],
                },
            }],
            "graph":{
                "nodes":[{
                    "id":"callback:onTrigger:1",
                    "kind":"callback",
                    "label":"timer · 1000",
                    "meta":{
                        "callback_type":"timer",
                        "callback_event":None,
                        "callback_delay_source":"1000",
                    },
                }],
            },
        }
        engine=behavior_engine_drilldown(inspected,server="topaz",source_root=root)
        assert engine["direct_call_count"]==3,engine
        assert engine["binding_counts"]=={"CASE_ONLY":1,"EXACT":1,"NOT_INDEXED":1},engine
        assert engine["case_only_call_count"]==1,engine
        assert engine["unindexed_call_count"]==1,engine
        assert engine["shared_helpers"][0]["api_calls"][0]["binding"]["status"]=="EXACT",engine
        assert engine["shared_helpers"][0]["callees"][0]["qualified_name"]=="xi.demo.inner",engine
        assert engine["callback_count"]==1,engine
        assert engine["callbacks"][0]["callback_type"]=="timer",engine

    print("Feature Trace binding/engine drilldown regression: PASS")


if __name__=="__main__":
    main()
