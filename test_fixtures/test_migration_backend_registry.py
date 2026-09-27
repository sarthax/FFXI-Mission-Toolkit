#!/usr/bin/env python3
"""Regression checks for explicit migration backend routing."""
from workbench.migrations.backend_registry import default_backend_registry


def main():
    registry=default_backend_registry()
    lua=registry.resolve("Topaz","DSP","Lua")
    sql=registry.resolve("TOPAZ","DSP","SQL")
    assert lua is not None and lua.backend_id=="legacy.topaz_to_dsp.lua",lua
    assert sql is not None and sql.backend_id=="legacy.topaz_to_dsp.sql",sql

    lsb_lua=registry.resolve("LSB","DSP","LUA")
    assert lsb_lua is not None and lsb_lua.backend_id=="conditional.lsb_to_dsp.lua",lsb_lua
    assert lsb_lua.support_level=="CONDITIONAL",lsb_lua
    assert registry.resolve("TOPAZ","LSB","LUA") is None

    result=lua.convert("local x = tpz.status.NORMAL\n")
    assert result.backend_id=="legacy.topaz_to_dsp.lua",result
    assert result.output,result

    safe=lsb_lua.convert("local x = 1\n")
    assert safe.status=="CONVERTED",safe
    framework=lsb_lua.convert("local mission = Mission:new(1, 2)\n")
    assert framework.status=="MANUAL_REQUIRED",framework
    xi_namespace=lsb_lua.convert("local x = xi.status.NORMAL\n")
    assert xi_namespace.status=="MANUAL_REQUIRED",xi_namespace

    matrix=registry.support_matrix(("TOPAZ","TOPAZ_NEXT","DSP","LSB"))
    routes={(r["source_family"],r["target_family"],r["artifact_type"]):r for r in matrix["routes"]}
    assert routes[("TOPAZ","DSP","LUA")]["support_level"]=="SUPPORTED",routes
    assert routes[("TOPAZ","DSP","SQL")]["support_level"]=="SUPPORTED",routes
    assert routes[("LSB","DSP","LUA")]["support_level"]=="CONDITIONAL",routes
    assert routes[("LSB","DSP","SQL")]["support_level"]=="UNSUPPORTED",routes
    assert routes[("TOPAZ_NEXT","DSP","LUA")]["support_level"]=="UNSUPPORTED",routes
    assert routes[("DSP","LSB","SQL")]["support_level"]=="UNSUPPORTED",routes
    assert all(r["backend_id"] is None for r in matrix["routes"] if r["support_level"]=="UNSUPPORTED")
    print("migration backend registry self-test: PASS")


if __name__=="__main__":
    main()
