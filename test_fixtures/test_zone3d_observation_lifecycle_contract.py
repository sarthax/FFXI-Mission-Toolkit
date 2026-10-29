"""Live entity disappearance is observation loss, not proof of server despawn."""
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_history_contract():
    assert 'id="zone3d-correlation-lifecycle"' in JS
    assert 'value="last_seen"' in JS
    assert "const OBSERVATION_HISTORY_SECONDS = 120;" in JS
    assert "function rememberLiveEntitySnapshot()" in JS
    assert "function clearObservationHistory()" in JS
    assert "lastLiveEntitiesById.clear()" in JS
    assert "if (!live.length && telemetryUsable && previous && now - previous.seenAt <= OBSERVATION_HISTORY_SECONDS && map.length <= 1) kind = 'last_seen';" in JS
    assert "not proof of despawn" in JS
    assert "rememberLiveEntitySnapshot();\n    updateLiveEntityPicker();" in JS
