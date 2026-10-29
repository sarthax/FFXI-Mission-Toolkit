from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "gui" / "templates" / "zone_view3d.html"


def test_zone_viewer_reports_mesh_origin_and_recoverable_failure():
    source = VIEWER.read_text(encoding="utf-8")
    assert 'id="viewer-mesh-source"' in source
    assert 'id="viewer-mesh-error"' in source
    assert 'id="viewer-retry-mesh"' in source
    assert "showMeshSource(`Client DAT · ${audit.accepted}/${audit.total} instances" in source
    assert "showMeshSource('Cached OBJ · untextured fallback')" in source
    assert "showMeshError('The cached OBJ is missing or unreadable." in source
    assert "loadObjFallback();" in source
    assert "window.location.reload()" in source
    assert "meshErrorDetailEl.textContent = detail" in source
