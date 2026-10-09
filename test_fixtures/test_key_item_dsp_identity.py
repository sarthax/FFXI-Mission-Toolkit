"""Regression coverage for fail-closed DSP-specific key-item source resolution."""
from pathlib import Path

from workbench.devtools.features.key_item_dsp_identity import resolve_dsp_key_item


def test_unique_dsp_name_match_does_not_assume_client_id(tmp_path: Path):
    file = tmp_path / "scripts" / "globals" / "keyitems.lua"
    file.parent.mkdir(parents=True)
    file.write_text("tpz = {}\n    TEST_KEY = 735,\n    OTHER_KEY = 736,\n", encoding="utf-8")
    result = resolve_dsp_key_item(tmp_path, "Test Key")
    assert result["status"] == "name_verified"
    assert result["symbol"] == "TEST_KEY"
    assert result["server_id"] == 735


def test_dsp_lookup_fails_closed_for_missing_and_ambiguous_identity(tmp_path: Path):
    missing = resolve_dsp_key_item(tmp_path, "Test Key")
    assert missing["symbol"] is None
    file = tmp_path / "scripts" / "globals" / "keyitems.lua"
    file.parent.mkdir(parents=True)
    file.write_text("    TEST_KEY = 12,\n    TEST_KEY = 13,\n", encoding="utf-8")
    ambiguous = resolve_dsp_key_item(tmp_path, "Test Key")
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["symbol"] is None


def test_dsp_api_requires_direct_source_verification():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    section = host.split("def keyitems_lua_references(", 1)[1].split("ZONE_BROWSE_PAGE_SIZE", 1)[0]
    assert "resolve_dsp_key_item(root, client_name)" in section
    assert 'identity["status"] != "name_verified"' in section
    assert 'lineage="dsp"' in section
    template = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'value="dsp"' in template
