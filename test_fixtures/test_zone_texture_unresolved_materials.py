from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_zone_parser_never_replaces_unresolved_material_with_majority_texture():
    source = (ROOT / "gui/static/ffxi-dat/ZoneFile.js").read_text(encoding="utf-8")
    assert "fallbackTexIdx" not in source
    assert "p.materialIndex = fallbackTexIdx" not in source
    assert "if (prefab.materialIndex !== -1) continue;" in source
    assert "textureDiagnostics:" in source
    assert "unresolvedNames:" in source
    assert 'missingTextureNames.set(name' in source


def test_viewer_reports_unresolved_texture_names_for_real_dat_diagnosis():
    viewer = (ROOT / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert "unresolved_texture_names: unresolved" in viewer
    assert "setMeshDiagnostics('client_dat'" in viewer
