from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_root(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    binding_index = importlib.import_module("workbench.validation.packages.binding_index")
    binding_audit = importlib.import_module("workbench.validation.packages.binding_audit")
    item_audit = importlib.import_module("workbench.validation.packages.item_audit")
    dev_index = importlib.import_module("workbench.devtools.server.binding_index")

    legacy_index = _load_root("backport_binding_index", REPO_ROOT / "backport_binding_index.py")
    legacy_audit = _load_root("backport_binding_audit", REPO_ROOT / "backport_binding_audit.py")
    legacy_item = _load_root("backport_item_audit", REPO_ROOT / "backport_item_audit.py")
    assert legacy_index is binding_index
    assert legacy_audit is binding_audit
    assert legacy_item.audit_package is item_audit.audit_package

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        topaz = root / "topaz"
        dsp = root / "dsp"
        package = root / "lua-dsp"
        (topaz / "src/map/lua").mkdir(parents=True)
        (dsp / "src/map/lua").mkdir(parents=True)
        package.mkdir()

        (topaz / "src/map/lua/lua_base_entity.cpp").write_text(
            'SOL_REGISTER("getID", CLuaBaseEntity::getID)\n'
            'SOL_REGISTER("PrintToPlayer", CLuaBaseEntity::PrintToPlayer)\n'
            'SOL_REGISTER("topazOnly", CLuaBaseEntity::topazOnly)\n',
            encoding="utf-8",
        )
        (dsp / "src/map/lua/lua_baseentity.cpp").write_text(
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\n'
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,printToPlayer)\n',
            encoding="utf-8",
        )

        assert binding_index.build_topaz_index(topaz) == dev_index.build_topaz_index(topaz)
        assert binding_index.build_dsp_index(dsp) == dev_index.build_dsp_index(dsp)

        meta = root / "dsp.meta.json"
        binding_index.write_index_metadata(meta, dsp, 2)
        assert binding_index.cache_matches_root(meta, dsp)
        (dsp / "src/map/lua/lua_baseentity.cpp").write_text(
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,getID)\n'
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,printToPlayer)\n'
            'LUNAR_DECLARE_METHOD(CLuaBaseEntity,setPos)\n',
            encoding="utf-8",
        )
        assert not binding_index.cache_matches_root(meta, dsp)

        topaz_cache = root / "topaz.json"
        dsp_cache = root / "dsp.json"
        topaz_cache.write_text(json.dumps(binding_index.build_topaz_index(topaz)), encoding="utf-8")
        dsp_cache.write_text(json.dumps(binding_index.build_dsp_index(dsp)), encoding="utf-8")
        diff = binding_index.classify_diff(topaz_cache, dsp_cache)
        assert diff["exact"] == ["getID"]
        assert diff["case_only"] == [("PrintToPlayer", "printToPlayer")]
        assert diff["topaz_only"] == ["topazOnly"]

        (package / "npc.lua").write_text(
            '-- prose fake :missingFromComment()\n'
            'function obj:helper() end\n'
            'player:getID()\n'
            'player:setPos(1, 2, 3)\n'
            'player:missingBinding()\n'
            'string.format("%s", "x")\n',
            encoding="utf-8",
        )
        calls = binding_audit.collect_method_calls(package)
        assert set(calls) == {"getID", "setPos", "missingBinding"}

        result = binding_audit.audit_package(package, dsp, "old_dsp_reference")
        assert [row[0] for row in result["confirmed"]] == ["getID", "setPos"]
        assert [row[0] for row in result["missing"]] == ["missingBinding"]

        # Item/content audit behavior against a synthetic target checkout.
        (dsp / "sql").mkdir(exist_ok=True)
        (dsp / "scripts/globals/items").mkdir(parents=True)
        (dsp / "scripts/globals").mkdir(parents=True, exist_ok=True)
        (dsp / "sql/item_basic.sql").write_text(
            "INSERT INTO `item_basic` VALUES (100,0,'good_item');\n"
            "INSERT INTO `item_basic` VALUES (101,0,'no_script');\n",
            encoding="utf-8",
        )
        (dsp / "scripts/globals/items/good_item.lua").write_text("return {}\n", encoding="utf-8")
        (dsp / "scripts/globals/keyitems.lua").write_text("GOOD_KEY = 1\n", encoding="utf-8")
        (dsp / "scripts/globals/shared.lua").write_text("return {}\n", encoding="utf-8")
        (package / "items.lua").write_text(
            "local GOOD_ITEM = 100\n"
            "local WARN_ITEM = 101\n"
            "local BAD_ITEM = 999\n"
            "player:hasKeyItem(GOOD_KEY)\n"
            "player:addKeyItem(MISSING_KEY)\n"
            "require(\"scripts/globals/shared\")\n"
            "require(\"scripts/globals/missing\")\n"
            "GetNPCByID(foo, instance)\n",
            encoding="utf-8",
        )
        item_result = item_audit.audit_package(package, dsp)
        assert [row[0] for row in item_result["missing_item_rows"]] == [999]
        assert [(row[0], row[1]) for row in item_result["missing_item_scripts"]] == [(101, "no_script")]
        assert [row[0] for row in item_result["missing_keyitems"]] == ["MISSING_KEY"]
        assert [row[0] for row in item_result["dangling_requires"]] == ["scripts/globals/missing"]
        assert len(item_result["bad_call_shapes"]) == 1

    code = (
        "from workbench.validation.packages import binding_index, binding_audit, item_audit; "
        "print(binding_index.classify_diff, binding_audit.audit_package, item_audit.audit_package)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
