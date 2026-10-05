from pathlib import Path

from workbench.editors.items import item_proc_sync as s


def _tree(tmp_path):
    d = tmp_path / "scripts/globals/items"
    d.mkdir(parents=True)
    (tmp_path / "scripts/globals/status.lua").write_text("EFFECT_POISON = 3\nSUBEFFECT_POISON = 1\n")
    return d


def test_misnamed_script_detected(tmp_path):
    d = _tree(tmp_path)
    (d / "poison_kukri _+1.lua").write_text("-- ID: 16489\nfunction onAdditionalEffect() end")
    assert s.find_misnamed(tmp_path, 16489, "poison_kukri_+1") == "scripts/globals/items/poison_kukri _+1.lua"
    assert s.find_misnamed(tmp_path, 1, "other") is None


def test_plan_misnamed_and_no_lsb(tmp_path):
    d = _tree(tmp_path)
    (d / "poison_kukri _+1.lua").write_text("-- ID: 16489\n")
    p = s.plan_item(16489, "poison_kukri_+1", tmp_path, tmp_path / "nolsb")
    assert p["state"] == "misnamed" and p["resolved"]["rename_to"].endswith("poison_kukri_+1.lua")
    assert s.plan_item(5, "x", tmp_path, tmp_path / "nolsb")["state"] == "no-lsb-data"


def test_generators_use_only_lsb_values():
    lua = s._lua_damage(1, "holy_sword", {"chance": 5, "damage": 10, "element": 7, "type": 1}, "LIGHT")
    assert "local chance = 5;" in lua and "local dmg = 10;" in lua and "SUBEFFECT_LIGHT_DAMAGE" in lua
    lua = s._lua_debuff(2, "x", {"chance": 15, "power": 4, "duration": 30, "status": 3}, "POISON", "WATER", "SUBEFFECT_POISON")
    assert "addStatusEffect(EFFECT_POISON, 4, 3, 30)" in lua
