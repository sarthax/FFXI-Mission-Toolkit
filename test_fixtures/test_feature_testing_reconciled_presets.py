from pathlib import Path

def test_presets_support_reference_and_literal_expected_values():
    html=(Path(__file__).resolve().parents[1]/'gui/templates/feature_testing.html').read_text(encoding='utf-8')
    assert "ft-design-preset" in html
    assert "ft-design-apply-preset" in html
    assert "const isRef=['db_bag','db_safe','approved_charid']" in html
    assert "$('ft-design-kind').value=isRef?'reference':'literal'" in html
    for preset in ('inventory_bag','inventory_safe','session','aura','stored'):
        assert preset in html
