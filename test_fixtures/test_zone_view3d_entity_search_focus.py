from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_focus_search_respects_original_spawn_indexes():
    Environment().parse(SOURCE)
    assert 'id="zone3d-focus-search"' in SOURCE
    assert 'id="zone3d-focus-count"' in SOURCE
    assert "spawnEntities.forEach((entity, index)" in SOURCE
    assert "option.value = String(index)" in SOURCE
    assert "const LIMIT = 250" in SOURCE
    assert "matched > LIMIT" in SOURCE
    assert "spawnEntities.indexOf(previousEntity)" in SOURCE
    assert "addEventListener('input', refreshFocusSpawn)" in SOURCE
    assert "spawnEntities.slice(0, 500)" not in SOURCE
