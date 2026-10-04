from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_weapon_effect_card_is_fail_closed_and_uses_existing_staging_path():
    js = (ROOT / "gui" / "static" / "itemedit_weapon_effects.js").read_text(encoding="utf-8")

    assert "Fire damage" in js and "Dark damage" in js
    assert "HP drain" in js and "MP drain" in js and "TP drain" in js
    assert "Self buff" in js and "Instant death" in js
    assert "if (lineage === 'LSB') return 'row-only';" in js
    assert "return 'verify-lineage';" in js
    assert "return 'server-code-required';" in js
    assert "mergeEffectRows('mods',rows)" in js
    assert "mergeEffectRows('latents',rows)" in js
    assert "/itemedit/save-atomic" not in js
    assert "Copy server handoff" in js


def test_weapon_effect_card_uses_structured_additional_effect_mod_ids():
    js = (ROOT / "gui" / "static" / "itemedit_weapon_effects.js").read_text(encoding="utf-8")
    for mod_id in (431, 499, 500, 501, 950, 951, 952, 953):
        assert str(mod_id) in js


def test_shared_shell_loads_guarded_weapon_effect_module():
    base = (ROOT / "gui" / "templates" / "base.html").read_text(encoding="utf-8")
    assert '/static/itemedit_weapon_effects.js' in base
