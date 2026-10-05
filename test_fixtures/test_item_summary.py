from workbench.editors.items import item_summary as isum


def _joyeuse(hit=2, desc="DMG:35 Delay:224\nOccasionally attacks twice"):
    return {"item_id": 17652,
            "server": {"item_basic": {"name": "joyeuse", "stackSize": 1},
                       "item_weapon": {"dmg": 35, "delay": 224, "skill": 3, "dmgType": 1, "hit": hit}},
            "mods": [{"modId": 61, "value": 14, "name": "DARKRES -- % Dark Resistance"}],
            "pet_mods": [], "latents": [], "client": {"name": "Joyeuse", "description": desc}}


def test_multi_hit_is_surfaced_and_no_gap_note():
    s = isum.summarize(_joyeuse())
    assert s["combat"]["multi_hit"]["text"] == "Occasionally attacks twice"
    assert s["combat"]["multi_hit"]["distribution_pct"] == {1: 55, 2: 45}
    assert s["bonuses"][0]["name"] == "DARKRES" and s["notes"] == []


def test_description_gap_is_flagged_not_guessed():
    s = isum.summarize(_joyeuse(hit=1))
    codes = {n["code"] for n in s["notes"]}
    assert {"DESC_MULTIHIT_NOT_IN_DATA", "DESC_DOUBLE_ATTACK_NOT_IN_DATA"} <= codes


def test_proc_switch_without_script_and_unknown_mod():
    d = _joyeuse()
    d["mods"] = [{"modId": 431, "value": 1, "name": "ADDITIONAL_EFFECT"}, {"modId": 9999, "value": 3, "name": None}]
    s = isum.summarize(d, script={"exists": False, "path": "scripts/globals/items/joyeuse.lua", "hooks": []})
    assert {"PROC_WITHOUT_SCRIPT", "UNKNOWN_MOD"} <= {n["code"] for n in s["notes"]}
    assert s["bonuses"][0]["name"] == "Unknown effect #9999" and s["script"]["proc_switch"] == 1
    assert any("[script missing]" in line for line in isum.summary_lines(s))


def test_latent_uses_meta_and_sets_pass_through():
    d = _joyeuse()
    d["latents"] = [{"modId": 61, "value": 5, "latentId": 0, "latentParam": 75, "name": "DARKRES",
                     "latentName": "HP_UNDER_PERCENT -- hp <= %"}]
    s = isum.summarize(d, special={"gear_sets": [{"set_id": 1, "comment": "T"}]},
                       latent_meta={0: {"comment": "hp less than or equal to %", "param_semantics": "hp percent"}})
    c = s["conditional_bonuses"][0]
    assert c["condition"] == "HP_UNDER_PERCENT" and c["param_meaning"] == "hp percent"
    assert s["set_bonuses"][0]["set_id"] == 1


def test_analyze_script_states():
    stub = "function onItemCheck(target)\n  return 0\nend\nfunction onItemUse(target)\n  -- TODO\nend\n"
    assert isum.analyze_script(stub)["state"] == "stub"
    check = "function onItemCheck(target)\n  if target:getHP() == 0 then return 56 end\n  return 0\nend\n"
    assert isum.analyze_script(check)["state"] == "check-only"
    real = "function onAdditionalEffect(player,target,damage)\n  target:addStatusEffect(EFFECT_POISON,3,3,30)\n  return 1,1,1\nend\n"
    a = isum.analyze_script(real)
    assert a["state"] == "behavior" and "addStatusEffect" in a["hooks"][0]["effect_calls"]
    assert isum.analyze_script(stub)["todo_marker"] is True


def test_find_script_health(tmp_path):
    d = tmp_path / "scripts/globals/items"; d.mkdir(parents=True)
    (d / "a.lua").write_text("function onItemUse(t)\n return 0\nend\n")
    (d / "b.lua").write_text("function onItemUse(t)\n t:addHP(50)\nend\n")
    assert isum.find_script(tmp_path, "a")["analysis"]["state"] == "stub"
    assert isum.find_script(tmp_path, "b")["analysis"]["state"] == "behavior"
    d2 = _joyeuse(); d2["mods"] = [{"modId": 431, "value": 1, "name": "ADDITIONAL_EFFECT"}]
    s = isum.summarize(d2, script=isum.find_script(tmp_path, "a"))
    assert s["script"]["health"] == "stub" and "PROC_WITHOUT_SCRIPT" in {n["code"] for n in s["notes"]}


def test_lsb_compare(tmp_path):
    from workbench.editors.items import item_lsb_compare as c
    (tmp_path / "sql").mkdir(); (tmp_path / "documentation").mkdir()
    (tmp_path / "documentation/mods_by_id.txt").write_text("    DEF = 1,  // d\n    SNAP_SHOT = 5, // s\n    STR = 8, // s\n")
    (tmp_path / "sql/item_mods.sql").write_text(
        "INSERT INTO `item_mods` VALUES (7,1,100); -- DEF\nINSERT INTO `item_mods` VALUES (7,8,3);\n")
    (tmp_path / "sql/item_weapon.sql").write_text("INSERT INTO `item_weapon` VALUES (7,'x',3,0,0,0,0,1,2,224,35,0);\n")
    c._lsb_mod_names.cache_clear(); c._lsb_rows.cache_clear()
    d = {"mods": [{"modId": 1, "value": 1, "name": "DEF"}, {"modId": 9, "value": 2, "name": "AGI"}],
         "server": {"item_weapon": {"skill": 3, "dmgType": 1, "hit": 1, "delay": 224, "dmg": 35}}}
    r = c.compare_with_lsb(7, d, tmp_path)
    kinds = {(x["mod"], x["kind"]) for x in r["mod_differences"]}
    assert kinds == {("DEF", "value"), ("STR", "lsb-only"), ("AGI", "dsp-only")}
    assert [x for x in r["mod_differences"] if x["mod"] == "DEF"][0]["hint"].startswith("LSB value is exactly 100x")
    assert [w["field"] for w in r["weapon_differences"]] == ["hit"]
