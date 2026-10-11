from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"

def test_alpha_cutout_uses_texture_data_not_blending_flag():
    text = VIEWER.read_text(encoding="utf-8")
    assert "const isCutout = hasTextureAlpha && partialAlphaPixels === 0;" in text
    assert "if (alpha < 255) alphaPixels++" in text
    assert "isCutout && { alphaTest: 0.5 }" in text
    assert "!isCutout && hasTextureAlpha && { transparent: true, depthWrite: false }" in text
    assert "alphaCutout: 0, alphaGradient: 0" in text
