from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_camera_navigation_stays_read_only_and_preserves_orientation():
    source = VIEWER.read_text(encoding="utf-8")
    for suffix in ("camera-readout", "goto-x", "goto-y", "goto-z", "goto", "save-view", "restore-view"):
        assert f'id="zone3d-{suffix}"' in source
    assert "new THREE.Vector3(values[0], -values[1], -values[2])" in source
    assert "values.every(Number.isFinite)" in source
    assert "camera.position.copy(savedCameraView.position)" in source
    assert "camera.quaternion.copy(savedCameraView.quaternion)" in source
    assert "controls.target.copy(savedCameraView.target)" in source
    assert "updateCameraReadout();" in source
    assert "Camera moved (viewer only)." in source
