from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_spawn_kind_visibility_and_capture_search_share_one_filter():
    source = VIEWER.read_text(encoding="utf-8")
    for kind in ("m", "n", "d", "c"):
        assert f'data-spawn-kind="{kind}" checked' in source
    assert "visibleKinds.has(e.k || 'c') && captureEntityMatches(e, q)" in source
    assert "toggle.addEventListener('change', refreshCaptureSpatialResults)" in source
    assert "spawnEntities = spawnEntitiesAll.filter(" in source
    assert "hoveredSpawnId = null;" in source
    assert "spawn-visibility-count" in source
