"""Initial pairing calculation must run after inspector is revealed."""
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_pairing_runs_after_open():
    inspect = TEXT.split("function inspectEntity(entity) {", 1)[1].split("const inspectorFeedback =", 1)[0]
    assert "entityInspector.hidden = false;\n  updateEntityPair();" in inspect
    assert inspect.count("updateEntityPair();") == 1
    assert "Live ↔ server spawn pair · correlation" in TEXT
