#!/usr/bin/env python3
"""Regression checks for explicit migration backend routing."""
from workbench.migrations.backend_registry import default_backend_registry


def main():
    registry=default_backend_registry()
    lua=registry.resolve("Topaz","DSP","Lua")
    sql=registry.resolve("TOPAZ","DSP","SQL")
    assert lua is not None and lua.backend_id=="legacy.topaz_to_dsp.lua",lua
    assert sql is not None and sql.backend_id=="legacy.topaz_to_dsp.sql",sql

    # Do not silently reuse a Topaz converter for LSB or another target family.
    assert registry.resolve("LSB","DSP","LUA") is None
    assert registry.resolve("TOPAZ","LSB","LUA") is None

    result=lua.convert("local x = tpz.status.NORMAL\n")
    assert result.backend_id=="legacy.topaz_to_dsp.lua",result
    assert result.output,result
    print("migration backend registry self-test: PASS")


if __name__=="__main__":
    main()
