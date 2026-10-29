from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_read_only_diagnostics_panel_covers_live_and_fallback_paths():
    source = VIEWER.read_text(encoding="utf-8")
    assert 'id="zone3d-mesh-diagnostics"' in source
    assert 'id="zone3d-diagnostics-content"' in source
    assert 'id="zone3d-copy-diagnostics"' in source
    assert "setMeshDiagnostics('client_dat', {" in source
    assert "setMeshDiagnostics('cached_obj'" in source
    assert "setMeshDiagnostics('unavailable'" in source
    assert "navigator.clipboard.writeText(value)" in source
    assert "meshDiagnosticsContent.textContent = JSON.stringify(meshDiagnosticsReport, null, 2)" in source
