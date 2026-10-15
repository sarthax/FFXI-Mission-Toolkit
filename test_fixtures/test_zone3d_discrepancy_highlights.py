"""Stage 2 map discrepancy overlay remains opt-in and source-qualified."""
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_discrepancy_overlay_contract():
    text = VIEW.read_text(encoding="utf-8")
    for label in ('zone3d-correlation-highlight', 'zone3d-correlation-legend',
                  'zone3d-correlation-coverage'):
        assert f'id="{label}"' in text
    assert "function applyCorrelationMapColors(rows)" in text
    assert "correlationHighlight.checked && correlationColors[kind]" in text
    assert "Map: capture-derived records (not authoritative configured spawns)" in text
    assert "current instance and observation range unverified" in text
    assert "correlationHighlight.addEventListener('change', refreshZoneCorrelation)" in text
    assert "applyCorrelationMapColors(zoneCorrelationRows())" in text
