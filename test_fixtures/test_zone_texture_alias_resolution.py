from pathlib import Path


ZONE_FILE = Path(__file__).resolve().parents[1] / "gui/static/ffxi-dat/ZoneFile.js"


def test_texture_alias_fallback_resolves_only_unique_names():
    source = ZONE_FILE.read_text(encoding="utf-8")
    assert "function uniqueTextureAliases(textureNameMap)" in source
    assert "aliases.set(alias, null)" in source
    assert "aliasIndex !== undefined && aliasIndex !== null" in source
    assert "mesh.materialIndex = -1;" in source
    assert "aliasMatchedCount" in source
    assert "fallbackTexIdx" not in source
