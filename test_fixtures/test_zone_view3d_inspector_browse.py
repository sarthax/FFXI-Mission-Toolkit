from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_inspector_browsing_and_marker_selection():
    Environment().parse(SOURCE)
    for ident in ["zone3d-inspector-prev", "zone3d-inspector-next", "zone3d-inspector-index"]:
        assert f'id="{ident}"' in SOURCE
    assert "function stepInspectedEntity(offset)" in SOURCE
    assert "spawnEntities.indexOf(selectedEntity)" in SOURCE
    assert "spawnEntities.length) % spawnEntities.length" in SOURCE
    assert "Not in visible markers" in SOURCE
    assert "e === selectedEntity ? 0xffff33" in SOURCE
    assert "e === entity ? 0xffff33" in SOURCE
    assert "spawnMesh.instanceColor.needsUpdate = true" in SOURCE
