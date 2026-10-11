from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_entity_search_shortcuts_preserve_text_input_and_pointer_lock():
    Environment().parse(SOURCE)
    assert 'id="zone3d-quick-find"' in SOURCE
    assert "function openEntitySearch()" in SOURCE
    assert "showTab('camera')" in SOURCE
    assert "focusGroup.open = true" in SOURCE
    assert "event.key === '/'" in SOURCE
    assert "event.key.toLowerCase() === 'f'" in SOURCE
    assert "target.isContentEditable" in SOURCE
    assert "document.pointerLockElement" in SOURCE
    assert "focusButton.click()" in SOURCE
