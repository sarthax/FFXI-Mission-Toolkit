from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_zone_chooser_in_header_without_zone_sidebar_tab():
    Environment().parse(SOURCE)
    identity = SOURCE.split("{% block page_identity %}", 1)[1].split("{% endblock %}", 1)[0]
    assert 'id="zone-select"' in identity
    assert 'data-viewer-tab="zone"' not in SOURCE
    assert 'data-viewer-pane="zone"' not in SOURCE
    assert "sections.get('capture').appendChild(zoneSwitch)" in SOURCE
    assert "window.location.href = '/zones/' + e.target.value + '/view3d'" in SOURCE
