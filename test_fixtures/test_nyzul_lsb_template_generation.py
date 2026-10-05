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
    assert "IS_LSB && boss ? 0" in TEXT


if __name__ == "__main__":
    test_template_routes_modern_lsb_through_generation_contract()
    test_legacy_generation_values_are_explicit_fallbacks_only()
    test_lsb_random_objectives_model_native_selection_rules()
    test_lsb_boss_and_gear_rules_are_adapter_driven()
    print("nyzul LSB template generation regression: ok")
