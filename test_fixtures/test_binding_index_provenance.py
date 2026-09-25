#!/usr/bin/env python3
"""Regression checks for binding-index cache provenance."""
from pathlib import Path
import json
import tempfile

import backport_binding_index as bbi


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        lua=root/"src"/"map"/"lua"
        lua.mkdir(parents=True)
        src=lua/"lua_baseentity.cpp"
        src.write_text("LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\n",encoding="utf-8")

        meta=root/"cache.meta.json"
        bbi.write_index_metadata(meta,root,1)
        assert bbi.cache_matches_root(meta,root)

        src.write_text("LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\nLUNAR_DECLARE_METHOD(CLuaBaseEntity,setPos)\n",encoding="utf-8")
        assert not bbi.cache_matches_root(meta,root)

        legacy=root/"legacy.meta.json"
        legacy.write_text(json.dumps({"schema":0})+"\n",encoding="utf-8")
        assert not bbi.cache_matches_root(legacy,root)

    print("binding index provenance self-test: PASS")


if __name__=="__main__":
    main()
