from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_viewpoint_controls_are_in_session_and_camera_only():
    source = VIEWER.read_text(encoding="utf-8")
    for suffix in ("view-name", "add-bookmark", "bookmark-list", "open-bookmark",
                   "delete-bookmark", "frame-zone", "focus-spawn", "focus-spawn-button"):
        assert f'id="zone3d-{suffix}"' in source
    assert "const namedViews = []" in source
    assert "namedViews.length >= 30" in source
    assert "restoreSnapshot(initialCameraView)" in source
    assert "camera.position.copy(view.position)" in source
    assert "camera.quaternion.copy(view.quaternion)" in source
    assert "controls.target.copy(view.target)" in source
    assert "refreshFocusSpawn();" in source
    assert "flyTo(new THREE.Vector3(entity.x, -entity.y, -entity.z))" in source
    assert "initialCameraView = snapshotView()" in source
