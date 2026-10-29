from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"

def test_read_only_viewer_reparents_existing_controls_into_collapsible_overlay():
    source = VIEWER.read_text(encoding="utf-8")
    assert 'id="zone3d-toolrail"' in source
    assert 'id="zone3d-drawer"' in source
    for tab in ("layers", "camera", "live", "capture", "diagnostics"):
        assert f'data-viewer-tab="{tab}"' in source
        assert f'data-viewer-pane="{tab}" hidden' in source
    for existing_control in ("#ashita-live-controls", "#zone3d-navigation",
                             "#capture-spatial-controls", "#zone3d-mesh-diagnostics",
                             "#spawn-visibility", "#tod-slider"):
        assert existing_control in source
    assert "sections.get(tab).appendChild(target)" in source
    assert "sections.get('layers').appendChild(layerGroup)" in source
    assert "panel.hidden = isOpen" in source
    assert "event.key === 'Escape'" in source
    assert '#zone3d-drawer[hidden],.zone3d-tab-pane[hidden]{display:none!important}' in source


def test_overlay_template_has_no_jinja_comment_delimiter_in_css():
    source = VIEWER.read_text(encoding="utf-8")
    assert "{#zone3d-" not in source
    assert "makeGroup('live', 'Axis and heading alignment'" in source
    assert "makeGroup('camera', 'Saved viewpoints'" in source
    from jinja2 import Environment
    Environment().parse(source)
