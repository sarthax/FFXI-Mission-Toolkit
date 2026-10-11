from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_live_defaults_heading_and_tracking():
    assert 'id="ashita-live-toggle" type="checkbox" checked' in TEMPLATE
    assert '<option value="0" selected>0°' in TEMPLATE
    assert '<option value="180" selected>' not in TEMPLATE


def test_entity_picker_not_rebuilt_every_telemetry_poll():
    assert "clearLiveEntities(true);" in TEMPLATE
    assert "liveEntitySelect.dataset.signature !== signature" in TEMPLATE
    assert "liveEntitySelect.dataset.signature = signature" in TEMPLATE
    assert "liveSelectedEntityId = liveEntitySelect.value === ''" in TEMPLATE
    assert "liveEntityInspect.disabled = liveEntitySelect.value === ''" in TEMPLATE


def test_toolbar_shortcuts_reuse_existing_safe_actions():
    assert 'id="zone3d-quick-player"' in TEMPLATE
    assert 'id="zone3d-quick-warp-target" disabled' in TEMPLATE
    assert "document.getElementById('ashita-live-focus').click()" in TEMPLATE
    assert "nw.el('nw-go').click()" in TEMPLATE
    assert "nw.el('zone3d-quick-warp-target').disabled = !(nw.armed && nw.target)" in TEMPLATE
