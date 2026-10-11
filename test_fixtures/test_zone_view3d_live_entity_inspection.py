from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_live_entity_inspection_and_disconnect_cleanup():
    Environment().parse(SOURCE)
    for ident in ("ashita-entity-select", "ashita-entity-inspect", "ashita-entity-count"):
        assert f'id="{ident}"' in SOURCE
    assert "const liveObservedEntities = []" in SOURCE
    assert "let liveSelectedEntityId = ''" in SOURCE
    assert "liveObservedEntities.findIndex" in SOURCE
    assert "inspectEntity(entity)" in SOURCE
    assert "liveEntityInspect.disabled = true" in SOURCE
    assert "liveObservedEntities.push({" in SOURCE
    assert "liveSelectedEntityId = '';" in SOURCE
