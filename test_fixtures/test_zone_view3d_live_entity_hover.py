from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_live_selection_color_is_per_marker_and_hover_uses_nearest_hit():
    Environment().parse(SOURCE)
    assert "liveEntityMaterial.clone()" in SOURCE
    assert "function highlightObservedEntity()" in SOURCE
    assert "active ? 0xffff33 : 0xf5a35c" in SOURCE
    assert "active ? 1.5 : 1" in SOURCE
    assert "marker.userData.liveEntityIndex" in SOURCE
    assert "raycaster.setFromCamera(pointerNdc, camera)" in SOURCE
    assert "liveHits[0].distance <= spawnHit.distance" in SOURCE
    assert "spawnTooltip.textContent = (entity.n || 'Live entity')" in SOURCE
