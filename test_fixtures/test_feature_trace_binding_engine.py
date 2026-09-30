#!/usr/bin/env python3
"""Executable regression for Feature Trace Lua -> binding -> engine drill-down."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile

from workbench.core.services import feature_trace_binding_drilldown as drill
from workbench.core.services.feature_trace_binding_drilldown import (
    binding_index_for_server,
    binding_lookup,
    behavior_engine_drilldown,
)


def _effect(method,line):
    return SimpleNamespace(
        effect="API_CALL",
        target="player",
        value=method,
        metadata={
            "qualified_name":f"player:{method}",
            "source_line":line,
            "source_line_text":f"player:{method}()",
        },
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
SOL_REGISTER("getID", CLuaOtherEntity::getID)
SOL_REGISTER("Foo", CLuaBaseEntity::Foo)
SOL_REGISTER("FOO", CLuaOtherEntity::FOO)

int32 CLuaBaseEntity::getID(lua_State* L)
{
    return 1;
}

int32 CLuaBaseEntity::getID(lua_State* L, int32 mode)
{
    return mode;
}

int32 CLuaBaseEntity::SetPos(lua_State* L)
{
    return 0;
}

int32 CLuaOtherEntity::getID(lua_State* L)
{
    return 2;
}

int32 CLuaBaseEntity::Foo(lua_State* L)
{
    return 3;
}

int32 CLuaOtherEntity::FOO(lua_State* L)
{
    return 4;
}
""".strip()+"\n",
            encoding="utf-8",
        )

        index=binding_index_for_server("topaz",root)
        assert set(index)=={"getID","SetPos","Foo","FOO"},index

        # 1-5: exact match, duplicate registrations, class/file summary, implementation
        # candidates, and first-candidate compatibility fields.
        exact=binding_lookup("topaz",root,"getID",index=index)
        assert exact["status"]=="EXACT",exact
        assert exact["location_count"]==2,exact
        assert exact["multiple_locations"] is True,exact
        assert exact["class_count"]==2,exact
        assert exact["classes"]==["CLuaBaseEntity","CLuaOtherEntity"],exact
        base=next(row for row in exact["locations"] if row["class"]=="CLuaBaseEntity")
        assert base["registration_excerpt"],base
        assert base["implementation_candidate_count"]==2,base
        assert base["implementation_line"]==base["implementation_candidates"][0]["line"],base
        assert "CLuaBaseEntity::getID" in base["implementation_excerpt"]["text"],base
        assert base["source_read_status"]=="READ",base

        # 6-8: deterministic case-only resolution and explicit case-collision ambiguity.
        case=binding_lookup("topaz",root,"setpos",index=index)
        assert case["status"]=="CASE_ONLY",case
        assert case["resolved_name"]=="SetPos",case
        assert case["candidate_names"]==["SetPos"],case
        collision=binding_lookup("topaz",root,"foo",index=index)
        assert collision["status"]=="CASE_AMBIGUOUS",collision
        assert collision["candidate_names"]==["FOO","Foo"],collision
        assert collision["location_count"]==2,collision
        assert {row["registered_name"] for row in collision["locations"]}=={"FOO","Foo"},collision

        # 9-10: a successful index with no method is distinct from an unavailable index.
        missing=binding_lookup("topaz",root,"doesNotExist",index=index)
        assert missing["status"]=="NOT_INDEXED",missing
        assert missing["locations"]==[],missing
        unavailable=binding_lookup(
            "topaz",root,"getID",index={},index_error="RuntimeError: synthetic index failure"
        )
        assert unavailable["status"]=="INDEX_UNAVAILABLE",unavailable
        assert "synthetic index failure" in unavailable["index_error"],unavailable

        # 11: empty method stays a separate input-quality state.
        no_method=binding_lookup("topaz",root,"",index=index)
        assert no_method["status"]=="NO_METHOD",no_method

        # 12: path containment/read status is explicit for an invalid indexed source.
        outside=binding_lookup(
            "topaz",root,"bad",
            index={"bad":[{"file":"../../outside.cpp","line":1,"class":"CLuaBad"}]},
        )
        assert outside["locations"][0]["source_read_status"]=="MISSING_OR_OUTSIDE_ROOT",outside

        # 13: DSP/LUNAR indexing remains supported.
        dsp_root=root/"dsp"
        dsp_lua=dsp_root/"src"/"map"/"lua"
        dsp_lua.mkdir(parents=True)
        (dsp_lua/"lua_baseentity.cpp").write_text(
            "LUNAR_DECLARE_METHOD(CLuaBaseEntity, getDSPID)\n",encoding="utf-8"
        )
        dsp_index=binding_index_for_server("dsp",dsp_root)
        assert "getDSPID" in dsp_index,dsp_index

        rule=SimpleNamespace(
            effects=(
                _effect("getID",3),
                _effect("setpos",4),
                _effect("doesNotExist",5),
                _effect("foo",6),
                _effect("getID",3),  # intentional duplicate observation
            ),
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
                    },{
                        "qualified_name":"player:doesNotExist",
                        "receiver":"player",
                        "function":"doesNotExist",
                        "line":12,
                        "source_line":"player:doesNotExist()",
                    }],
                    "shared_helper_callees":[{
                        "qualified_name":"xi.demo.inner",
                        "status":"UNRESOLVED",
                    }],
                },
            }],
            "graph":{
                "nodes":[{
                    "id":"callback:z",
                    "kind":"callback",
                    "label":"timer · 1000",
                    "meta":{
                        "callback_type":"timer",
                        "callback_event":None,
                        "callback_delay_source":"1000",
                    },
                },{
                    "id":"callback:a",
                    "kind":"callback",
                    "label":"event · finish",
                    "meta":{
                        "callback_type":"event",
                        "callback_event":"finish",
                        "callback_delay_source":None,
                    },
                }],
            },
        }
        engine=behavior_engine_drilldown(inspected,server="topaz",source_root=root)

        # 14-20: engine summary preserves dedupe, ambiguity, multi-location, helper,
        # callback ordering, index status, and review-state counts.
        assert engine["raw_direct_call_count"]==5,engine
        assert engine["direct_call_count"]==4,engine
        assert engine["duplicate_direct_call_count"]==1,engine
        assert engine["binding_counts"]=={
            "CASE_AMBIGUOUS":1,"CASE_ONLY":1,"EXACT":1,"NOT_INDEXED":1
        },engine
        assert engine["case_only_call_count"]==1,engine
        assert engine["case_ambiguous_call_count"]==1,engine
        assert engine["unindexed_call_count"]==1,engine
        assert engine["multi_location_call_count"]==1,engine
        assert engine["binding_index_status"]=="READY",engine
        assert engine["binding_index_error"] is None,engine
        assert engine["helper_binding_counts"]=={"EXACT":1,"NOT_INDEXED":1},engine
        assert engine["shared_helpers"][0]["api_calls"][0]["binding"]["status"]=="EXACT",engine
        assert engine["shared_helpers"][0]["callees"][0]["qualified_name"]=="xi.demo.inner",engine
        assert engine["callback_count"]==2,engine
        assert [cb["callback_type"] for cb in engine["callbacks"]]==["event","timer"],engine

        # Index-build exceptions must propagate as INDEX_UNAVAILABLE, never NOT_INDEXED.
        original=drill.backport_binding_index.build_topaz_index
        try:
            def boom(_root):
                raise RuntimeError("synthetic provider failure")
            drill.backport_binding_index.build_topaz_index=boom
            failed=behavior_engine_drilldown(inspected,server="topaz",source_root=root)
        finally:
            drill.backport_binding_index.build_topaz_index=original
        assert failed["binding_index_status"]=="UNAVAILABLE",failed
        assert failed["unavailable_call_count"]==4,failed
        assert failed["unindexed_call_count"]==0,failed
        assert all(row["binding"]["status"]=="INDEX_UNAVAILABLE" for row in failed["direct_calls"]),failed

    print("Feature Trace binding/engine drilldown regression: PASS")


if __name__=="__main__":
    main()
