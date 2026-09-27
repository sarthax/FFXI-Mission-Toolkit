#!/usr/bin/env python3
"""Regression checks for symbol-aware entity identity drift."""
from pathlib import Path
import tempfile
from workbench.adapters.servers.entity_symbols import lua_numeric_symbols, yaml_npc_script_symbols
from workbench.migrations.entity_identity import compare_symbol_maps
from workbench.migrations.logical_planner import plan_entity_identity_drifts

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        lua=root/"IDs.lua"
        yaml=root/"npcs.yaml"
        lua.write_text("""
    _jr1 = 17035541,
    _1rx = 17035537,
    STABLE = 100,
""",encoding="utf-8")
        yaml.write_text("""
npcs:
  17035542:
    script: _jr1
  17035538:
    script: _1rx
  100:
    script: STABLE
""",encoding="utf-8")
        source=yaml_npc_script_symbols(yaml)
        target=lua_numeric_symbols(lua)
        diff=compare_symbol_maps(source,target)
        renumbered={d.symbol:(d.source_id,d.target_id) for d in diff["renumbered"]}
        assert renumbered["_jr1"]==(17035542,17035541),renumbered
        assert renumbered["_1rx"]==(17035538,17035537),renumbered
        assert diff["stable"]==[{"symbol":"STABLE","entity_id":100}],diff
        actions=plan_entity_identity_drifts(diff["renumbered"],"m")
        assert len(actions)==2,actions
        assert all(a.action=="RENUMBER" and a.status=="AUTO_MIGRATABLE" for a in actions),actions
        assert {a.metadata["match_basis"] for a in actions}=={"SYMBOL_IDENTITY"},actions
    print("entity symbol identity self-test: PASS")

if __name__=="__main__":
    main()
