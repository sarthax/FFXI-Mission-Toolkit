#!/usr/bin/env python3
"""Regression checks for binding-index cache provenance and Development scanner parity."""
from pathlib import Path
import json
import tempfile

from workbench.validation.packages import binding_index as bbi
from workbench.devtools.server import binding_index as dev_binding_index


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        lua=root/"src"/"map"/"lua"
        lua.mkdir(parents=True)
        src=lua/"lua_baseentity.cpp"
        src.write_text(
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\n'
            'SOL_REGISTER("getName", CLuaBaseEntity::getName)\n',
            encoding="utf-8",
        )

        # Development read-only scanner must preserve the exact registration inventory used by
        # Validation's cache/diff policy without depending on a root compatibility module.
        assert dev_binding_index.build_dsp_index(root)==bbi.build_dsp_index(root)
        assert dev_binding_index.build_topaz_index(root)==bbi.build_topaz_index(root)
        assert dev_binding_index.binding_source_fingerprint(root)==bbi.binding_source_fingerprint(root)

        meta=root/"cache.meta.json"
        bbi.write_index_metadata(meta,root,2)
        assert bbi.cache_matches_root(meta,root)

        src.write_text(
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\n'
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,setPos)\n'
            'SOL_REGISTER("getName", CLuaBaseEntity::getName)\n',
            encoding="utf-8",
        )
        assert not bbi.cache_matches_root(meta,root)
        assert dev_binding_index.build_dsp_index(root)==bbi.build_dsp_index(root)
        assert dev_binding_index.build_topaz_index(root)==bbi.build_topaz_index(root)

        legacy=root/"legacy.meta.json"
        legacy.write_text(json.dumps({"schema":0})+"\n",encoding="utf-8")
        assert not bbi.cache_matches_root(legacy,root)

    print("binding index provenance self-test: PASS")


if __name__=="__main__":
    main()
