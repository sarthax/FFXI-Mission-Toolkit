from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_inspector_copy_focus_search_actions():
    Environment().parse(SOURCE)
    for id_ in ["zone3d-inspector-focus", "zone3d-inspector-copy-id",
                "zone3d-inspector-copy-xyz", "zone3d-inspector-search",
                "zone3d-inspector-feedback"]:
        assert f'id="{id_}"' in SOURCE
    assert "navigator.clipboard.writeText(value)" in SOURCE
    assert "selectedEntity.x, -selectedEntity.y, -selectedEntity.z" in SOURCE
    assert "search.dispatchEvent(new Event('input', { bubbles: true }))" in SOURCE
    assert "document.getElementById('zone3d-quick-find').click()" in SOURCE
    assert "document.getElementById('zone3d-inspector-copy-xyz').disabled = !hasPosition" in SOURCE
    assert "inspectEntity(e);" in SOURCE
