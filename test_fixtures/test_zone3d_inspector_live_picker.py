"""3D viewer inspector keeps live search and selection discoverable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gui/templates/zone_view3d.html"


def test_inspector_live_picker_contract():
    text = SOURCE.read_text(encoding="utf-8")
    assert 'id="zone3d-inspector-live-search"' in text
    assert 'id="zone3d-inspector-live-select"' in text
    assert 'id="zone3d-inspector-live-open"' in text
    assert "refreshInspectorLivePicker();" in text
    assert "liveEntityAgeSeconds(e) <= 3" in text
    assert "syncSelectOptions(inspectorLiveSelect" in text
    assert "inspectEntity(e);" in text
    assert "liveSelectedEntityId = liveEntityIdentity(e);" in text
    assert "if (entity.live_observation)" in text
