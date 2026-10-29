"""Observed entity picker must refresh without toggling nearby stream."""
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_live_picker_refresh_hooks():
    src = VIEW.read_text(encoding="utf-8")
    assert 'id="zone3d-inspector-live-refresh"' in src
    assert "inspectorLiveSelect.addEventListener('focus', refreshInspectorLivePicker)" in src
    assert "refreshInspectorLivePicker();\n  if (entity.live_observation)" in src
    assert "delete inspectorLiveSelect.dataset.signature;" in src
    assert "value: liveEntityIdentity(e)" in src
    assert "inspectorLiveCount.textContent = 'No live entities received'" in src
