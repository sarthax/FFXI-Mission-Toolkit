from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "gui" / "templates" / "nyzul_plot.html"
TEXT = TEMPLATE.read_text(encoding="utf-8")


def test_template_routes_modern_lsb_through_generation_contract():
    assert "const IS_LSB = D.adapter?.lineage === 'lsb';" in TEXT
    assert "const GEN = D.generation || {};" in TEXT
    assert "const SEL = GEN.selection || {};" in TEXT
    assert "SEL.non_boss_layout" in TEXT
    assert "SEL.boss_floor" in TEXT
    assert "SEL.gear_objective?.probability" in TEXT
    assert "GEN.boss_floor?.boss_spawn?.position" in TEXT
    assert "GEN.boss_floor?.rampart_spawn?.position" in TEXT
    assert "GEN.editor_objective_to_native" in TEXT
    assert "GEN.editor_objective_symbols" in TEXT


def test_legacy_generation_values_are_explicit_fallbacks_only():
    assert "const LEGACY_RULES" in TEXT
    assert "nonBossLayout:{first:1,last:15}" in TEXT
    assert "boss:{interval:20,layout:16}" in TEXT
    assert "gearProbability:.20" in TEXT
    assert "bossPos:[-390.5986,0,-380.1431]" in TEXT
    assert "rampartPos:[-406.7906,0,-365.0887]" in TEXT
    assert "boss ? 16 : rint(1,15)" not in TEXT
    assert "rnd()*100<=20 ? rint(1,2) : 0" not in TEXT
    assert "p:[-390.5986,0,-380.1431]" not in TEXT
    assert "p:[-406.7906,0,-365.0887]" not in TEXT


def test_lsb_random_objectives_model_native_selection_rules():
    assert "function randomEditorObjective()" in TEXT
    assert "SEL.free_floor" in TEXT
    assert "lsbFreeFloorSeen" in TEXT
    assert "SEL.normal_objectives" in TEXT
    assert "suppress_immediate_repeat" in TEXT
    assert "lsbPreviousNativeStage" in TEXT
    assert "nativeStage" in TEXT
    assert "nativeStageSymbol" in TEXT
    assert "Random (native LSB rules)" in TEXT


def test_lsb_boss_and_gear_rules_are_adapter_driven():
    assert "floor%(BOSS_RULE.interval || 20)===0" in TEXT
    assert "BOSS_RULE.layout ?? 16" in TEXT
    assert "NON_BOSS_LAYOUT.first ?? 1" in TEXT
    assert "NON_BOSS_LAYOUT.last ?? 15" in TEXT
    assert "p:BOSS_POS" in TEXT
    assert "p:RAMPART_POS" in TEXT
    assert "rnd() < GEAR_PROB" in TEXT
    assert "nativeStage !== D.objectives?.FREE_FLOOR" in TEXT


def test_lsb_normal_floor_uses_one_shared_spawn_pool_and_fodder_phase():
    assert "const shared = IS_LSB || $('shared').checked" in TEXT
    assert "$('shared').checked = true" in TEXT
    assert "$('shared').disabled = true" in TEXT
    assert "function lsbFodder(markTarget=false)" in TEXT
    assert "rint(6,12)" in TEXT
    assert "lsbFodder(stage===6)" in TEXT
    assert "regular fodder" in TEXT
    assert "if (!IS_LSB || lsbNormalFloor)" in TEXT


def test_lsb_specified_group_uses_random_subset_not_entire_group():
    assert "const amount=Math.min(g.count,rint(2,g.count))" in TEXT
    assert "ids.splice(mi,1)" in TEXT
    assert "else { enemyLayout();" in TEXT


def test_lsb_free_and_boss_floors_skip_random_gear_and_nms():
    assert "const lsbNormalFloor = !IS_LSB || (!boss && nativeStage !== D.objectives?.FREE_FLOOR);" in TEXT
    assert "gear<0) gear = lsbNormalFloor && rnd() < GEAR_PROB" in TEXT
    assert "if (!IS_LSB || lsbNormalFloor)" in TEXT


def test_clear_resets_lsb_run_state():
    assert "lsbFreeFloorSeen=false" in TEXT
    assert "lsbPreviousNativeStage=null" in TEXT


if __name__ == "__main__":
    test_template_routes_modern_lsb_through_generation_contract()
    test_legacy_generation_values_are_explicit_fallbacks_only()
    test_lsb_random_objectives_model_native_selection_rules()
    test_lsb_boss_and_gear_rules_are_adapter_driven()
    test_lsb_normal_floor_uses_one_shared_spawn_pool_and_fodder_phase()
    test_lsb_specified_group_uses_random_subset_not_entire_group()
    test_lsb_free_and_boss_floors_skip_random_gear_and_nms()
    test_clear_resets_lsb_run_state()
    print("nyzul LSB template generation regression: ok")
