from pathlib import Path

def test_guide_and_presets_coexist():
    from workbench.server_admin.feature_testing.test_specifications import _ALLOWED_OBSERVATIONS
    html=(Path(__file__).resolve().parents[1]/'gui/templates/feature_testing.html').read_text(encoding='utf-8')
    for marker in ('ft-observation-guide','ft-guide-use-field','ft-design-preset','ft-design-apply-preset'):
        assert marker in html
    for field in _ALLOWED_OBSERVATIONS:
        assert field+':[' in html
