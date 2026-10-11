from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_live_position_smoothing_is_read_only_and_stale_bounded():
    source = VIEWER.read_text(encoding="utf-8")
    assert "function updateLiveDisplay(frameSeconds)" in source
    assert "liveDisplayPosition.lerp(liveDisplayTarget, alpha)" in source
    assert "if (performance.now() - liveLastSampleAt > 2500) return" in source
    assert "liveDisplayPosition.distanceTo(current) > 100" in source
    assert "updateLiveDisplay(frameSeconds)" in source
    assert "liveDisplayTarget = null" in source
    assert "camera.position.add(delta)" in source
    assert "controls.target.copy(current)" in source
    assert "'/live-client/bridge/projection?client_id='" in source


def test_live_polling_is_serialized_so_slow_responses_are_not_starved():
    source = VIEWER.read_text(encoding="utf-8")
    assert "let livePollInFlight = false" in source
    assert "if (livePollInFlight) return" in source
    assert "livePollInFlight = true" in source
    assert "finally {\n    livePollInFlight = false;" in source
