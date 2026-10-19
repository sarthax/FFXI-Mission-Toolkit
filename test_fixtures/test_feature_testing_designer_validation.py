from pathlib import Path

def test_reference_picker_and_validation_messages():
    html=(Path(__file__).resolve().parents[1]/'gui/templates/feature_testing.html').read_text(encoding='utf-8')
    assert 'ft-design-kind' in html
    assert 'ft-design-reference' in html
    assert 'ft-design-validation' in html
    assert 'Add at least one assertion' in html
