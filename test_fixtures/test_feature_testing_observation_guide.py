from pathlib import Path

def test_observation_guide_has_all_spec_fields():
    from workbench.server_admin.feature_testing.test_specifications import _ALLOWED_OBSERVATIONS
    html=(Path(__file__).resolve().parents[1]/'gui/templates/feature_testing.html').read_text(encoding='utf-8')
    assert 'ft-observation-guide' in html
    assert 'ft-guide-use-field' in html
    assert 'Capture availability must be verified separately' in html
    for name in _ALLOWED_OBSERVATIONS:
        assert name+':[' in html or name+':'+'[' in html
