#!/usr/bin/env python3
"""Regression coverage for snapshot capability producers."""
from pathlib import Path
import sqlite3
import tempfile

from workbench.adapters.servers import TOPAZ
from workbench.adapters.servers.schema_coverage import persist_profile_mapping_coverage
from workbench.analyzers.server.binding_compatibility import compare_bindings
from workbench.core import graph
from workbench.core.services.capability_producers import persist_binding_compatibility_capabilities
from workbench.migrations.live_target_validation import persist_live_validation


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        db=root/"workbench.db"

        schema_result=persist_profile_mapping_coverage(TOPAZ,db,snapshot_id="snap:topaz")
        assert schema_result["observations"]>0,schema_result

        source={
            "source_snapshot_id":"snap:src",
            "bindings":[{
                "binding_id":"binding:src","lua_name":"getID","binding_system":"SOL2",
                "cpp_symbol":"CLuaBaseEntity::getID","class_name":"CLuaBaseEntity",
                "function_id":"fn:src","source_snapshot_id":"snap:src",
                "path":"lua.cpp","line":10,"evidence_id":"ev:src",
            }],
            "functions":[{
                "function_id":"fn:src","qualified_name":"CLuaBaseEntity::getID","name":"getID",
                "class_name":"CLuaBaseEntity","source_snapshot_id":"snap:src","path":"lua.cpp","line":20,
                "definition":True,"signature":{"return_type":"uint32","parameters":[]},
            }],
        }
        target={
            "source_snapshot_id":"snap:dst",
            "bindings":[{
                "binding_id":"binding:dst","lua_name":"getID","binding_system":"SOL2",
                "cpp_symbol":"CLuaBaseEntity::getID","class_name":"CLuaBaseEntity",
                "function_id":"fn:dst","source_snapshot_id":"snap:dst",
                "path":"lua.cpp","line":11,"evidence_id":"ev:dst",
            }],
            "functions":[{
                "function_id":"fn:dst","qualified_name":"CLuaBaseEntity::getID","name":"getID",
                "class_name":"CLuaBaseEntity","source_snapshot_id":"snap:dst","path":"lua.cpp","line":21,
                "definition":True,"signature":{"return_type":"uint32","parameters":[]},
            }],
        }
        payload=compare_bindings(source,target)
        con=graph.init_db(db)
        persist_binding_compatibility_capabilities(con,payload)
        con.close()

        live_payload={
            "logical_type":"item_basic",
            "target_table":"item_basic",
            "target_snapshot_id":"snap:live",
            "status":"VERIFIED",
            "results":[{"status":"VERIFIED"}],
        }
        persist_live_validation(
            live_payload,db,run_id="run:live:cap",
            target_snapshot_id="snap:live",
        )

        con=sqlite3.connect(db)
        schema_obs=con.execute(
            "SELECT status FROM capability_observations "
            "WHERE capability_id='capability:server-schema:item_basic' AND source_snapshot_id='snap:topaz'"
        ).fetchone()
        assert schema_obs is not None,schema_obs

        bind_obs=con.execute(
            "SELECT status,value_json FROM capability_observations "
            "WHERE source_snapshot_id='snap:dst' AND capability_id LIKE 'capability:lua-binding:%'"
        ).fetchone()
        assert bind_obs is not None and bind_obs[0]=="INFERRED",bind_obs

        live_obs=con.execute(
            "SELECT status FROM capability_observations "
            "WHERE capability_id='capability:live-target:item_basic' AND source_snapshot_id='snap:live'"
        ).fetchone()
        assert live_obs==("VERIFIED",),live_obs
        con.close()

    print("snapshot capability producers self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
