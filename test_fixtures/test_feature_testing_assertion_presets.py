from pathlib import Path

def test_guided_assertion_templates_present():
    html=(Path(__file__).resolve().parents[1]/"gui/templates/feature_testing.html").read_text(encoding="utf-8")
    for name in ("ft-design-preset","ft-design-apply-preset","inventory_bag","inventory_safe","session","aura","stored"):
        assert name in html
