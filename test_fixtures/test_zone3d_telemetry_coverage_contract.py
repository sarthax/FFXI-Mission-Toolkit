"""Do not infer a map-only missing entity without fresh client coverage."""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_missing_telemetry_is_unverified():
    assert 'value="unverified"' in SRC
    assert "now - liveEntitySnapshotAt <= 3" in SRC
    assert "if (!live.length && !telemetryUsable) kind = 'unverified';" in SRC
    assert "if (!live.length && telemetryUsable && previous" in SRC
    assert "map-only classifications suspended" in SRC
    assert "btn.disabled = row.kind === 'unverified'" in SRC
