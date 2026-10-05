from pathlib import Path

from workbench.editors.items import _special_cases as sc


def _tree(tmp_path):
    g = tmp_path / "scripts" / "globals"
    (g / "items").mkdir(parents=True)
    (tmp_path / "src" / "map").mkdir(parents=True)
    (g / "gear_sets.lua").write_text(
        "local GearSets = {\n {id = 1, items = {16092,14554}, matches = 2, matchType = 0, mods = {{MOD_HASTE_GEAR, 50, 0, 0}} }, -- Test set\n}\n")
    (g / "items" / "stew.lua").write_text(
        "function onEffectGain(target,effect)\n    target:addMod(MOD_STR, 5);\n    target:addMod(MOD_INT, -2);\nend\n")
    (tmp_path / "src" / "map" / "a.cpp").write_text("if (PItem->getID() == 15157) {}\n// getID() == 15158\n")
    return tmp_path


def test_special_cases(tmp_path):
    sc.clear_cache()
    r = sc.special_cases(_tree(tmp_path), 16092, "stew")
    assert r["gear_sets"][0]["comment"] == "Test set" and r["gear_sets"][0]["mods"][0]["value"] == 50
    assert [(m["mod"], m["value"]) for m in r["effect_gain_mods"]] == [("MOD_STR", 5.0), ("MOD_INT", -2.0)]
    assert sc.special_cases(tmp_path, 15157)["code_references"][0]["line"] == 1
    assert sc.special_cases(tmp_path, 15158)["code_references"] == []
    sc.clear_cache()
