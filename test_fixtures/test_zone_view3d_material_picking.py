from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_material_diagnostics_live_in_info_and_picker_is_read_only():
    Environment().parse(SOURCE)
    assert "['diagnostics', '#zone3d-alpha-tools']" in SOURCE
    assert "Disable transparency (debug)" in SOURCE
    assert 'id="zone3d-pick-material"' in SOURCE
    assert "raycaster.intersectObjects(sceneryMeshes, false)" in SOURCE
    assert "materialRowByMaterial.set(material, rowIndex)" in SOURCE
    assert "sceneryMeshes.push(mesh)" in SOURCE
    assert "alphaDiagnosticSelect.dispatchEvent(new Event('change'))" in SOURCE
