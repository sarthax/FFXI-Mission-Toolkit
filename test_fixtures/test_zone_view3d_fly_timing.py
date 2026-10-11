from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_fly_navigation_uses_frame_delta_and_normalized_direction():
    source = VIEWER.read_text(encoding="utf-8")
    assert "const frameSeconds = Math.min(clock.getDelta(), 0.05)" in source
    assert "camera.position.addScaledVector(dir.normalize(), flySpeed * 60 * frameSeconds)" in source
    assert "if (walking) dir.y = 0" in source
    assert "dir.lengthSq() > 0" in source
    assert "const t = clock.elapsedTime;" in source
    assert "if (moveState.forward) dir.z -= 1" in source
    assert "if (moveState.right) dir.x += 1" in source
