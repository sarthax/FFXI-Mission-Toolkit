from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_live_marker_selection_uses_current_pointer_and_nearest_hit():
    Environment().parse(SOURCE)
    assert "marker.userData.liveEntityIndex = liveObservedEntities.length - 1" in SOURCE
    assert "raycaster.setFromCamera(pointerNdc, camera)" in SOURCE
    assert "raycaster.intersectObjects(liveEntityPool.filter(x => x.visible), false)" in SOURCE
    assert "liveHit.distance <= spawnHit.distance" in SOURCE
    assert "liveSelectedEntityId = liveEntityIdentity(e)" in SOURCE
    assert "inspectEntity(entity)" in SOURCE
    assert "flyTo(new THREE.Vector3(entity.x, -entity.y, -entity.z))" in SOURCE
