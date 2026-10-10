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


def test_active_dsp_is_primary_for_catalog_and_lua_lookup():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    route = host.split('def keyitems(request: Request, q:', 1)[1].split('@app.get("/keyitems/lua-references.json")', 1)[0]
    assert 'get_active_server_identity()' in route
    assert 'active.get("family") == "dsp"' in route
    assert 'resolve_dsp_key_item(dsp_root, row["name"])' in route
    assert '"primary_dsp": primary_dsp' in route
    lookup = host.split('def keyitems_lua_references(', 1)[1].split('ZONE_BROWSE_PAGE_SIZE', 1)[0]
    assert 'selected.get("server_root") if selected.get("family") == "dsp"' in lookup
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'DSP checkout is primary' in page
    assert 'DSP (active)' in page
    assert 'active_server.server_root' in page


def test_dsp_enum_uses_metadata_cached_catalog(tmp_path: Path):
    from workbench.devtools.features.key_item_dsp_identity import _enum_records
    file = tmp_path / "scripts" / "globals" / "keyitems.lua"
    file.parent.mkdir(parents=True)
    file.write_text("    FIRST_KEY = 75,\n    SECOND_KEY = 76,\n", encoding="utf-8")
    _enum_records.cache_clear()
    first = resolve_dsp_key_item(tmp_path, "First Key")
    hits = _enum_records.cache_info().hits
    second = resolve_dsp_key_item(tmp_path, "Second Key")
    assert first["server_id"] == 75 and second["server_id"] == 76
    assert _enum_records.cache_info().hits > hits


def test_dsp_primary_display_does_not_mislabel_dsp_as_lsb():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'DSP checkout is primary' in page
    assert 'Topaz readiness (reference)' in page
    assert 'this ID maps to a different enum in the selected source' in page
    assert 'this id is really something else in LSB' not in page


def test_uploaded_dsp_semicolon_style_catalog(tmp_path: Path):
    """Real DSP keyitems.lua uses top-level assignments ending in semicolons."""
    from workbench.devtools.features.key_item_dsp_identity import _enum_records
    file = tmp_path / "scripts" / "globals" / "keyitems.lua"
    file.parent.mkdir(parents=True)
    file.write_text(
        "-- KEYITEMS IDS\n"
        "ZERUHN_REPORT = 1;\n"
        "AIRSHIP_PASS = 8;\n"
        "MOGHANCEMENT_MANDRAGORA_MANIA = 543; -- tentative name\n"
        "MAP_OF_ESCHA_ZITAH = 2307,\n"
        "MYSTERIOUS_AMULET = 579;\n"
        "MYSTERIOUS_AMULET = 708;\n", encoding="utf-8"
    )
    _enum_records.cache_clear()
    assert resolve_dsp_key_item(tmp_path, "Zeruhn Report")["server_id"] == 1
    assert resolve_dsp_key_item(tmp_path, "Airship Pass")["symbol"] == "AIRSHIP_PASS"
    assert resolve_dsp_key_item(tmp_path, "Moghancement Mandragora Mania")["server_id"] == 543
    assert resolve_dsp_key_item(tmp_path, "Map of Escha Zitah")["server_id"] == 2307
    ambiguous = resolve_dsp_key_item(tmp_path, "Mysterious Amulet")
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["symbol"] is None


def test_dsp_catalog_health_reports_missing_and_duplicate_names(tmp_path: Path):
    from workbench.devtools.features.key_item_dsp_identity import inspect_dsp_key_item_catalog
    assert inspect_dsp_key_item_catalog(tmp_path)["status"] == "unavailable"
    file = tmp_path / "scripts" / "globals" / "keyitems.lua"
    file.parent.mkdir(parents=True)
    file.write_text(
        "ZERUHN_REPORT = 1;\n"
        "AIRSHIP_PASS = 8;\n"
        "AIRSHIP_PASS = 99; -- duplicate constant\n", encoding="utf-8"
    )
    result = inspect_dsp_key_item_catalog(tmp_path)
    assert result["status"] == "ready"
    assert result["entries"] == 3
    assert result["unique_names"] == 1
    assert result["ambiguous_names"] == 1
    assert result["source_path"] == "scripts/globals/keyitems.lua"


def test_key_items_page_shows_active_dsp_catalog_health():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "dsp_catalog_health.entries" in page
    assert "dsp_catalog_health.ambiguous_names" in page
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert '"dsp_catalog_health": dsp_catalog_health' in host


def test_dsp_catalog_reports_reused_numeric_ids_and_ambiguous_names(tmp_path: Path):
    from workbench.devtools.features.key_item_dsp_identity import inspect_dsp_key_item_catalog
    source = tmp_path / "scripts" / "globals" / "keyitems.lua"
    source.parent.mkdir(parents=True)
    source.write_text(
        "FIRST_KEY = 1;\n"
        "SECOND_KEY = 1;\n"
        "THIRD_KEY = 3;\n"
        "THIRD_KEY = 4;\n", encoding="utf-8"
    )
    health = inspect_dsp_key_item_catalog(tmp_path)
    assert health["entries"] == 4
    assert health["unique_names"] == 2
    assert health["ambiguous_names"] == 1
    assert health["duplicate_numeric_ids"] == 1
    assert health["duplicate_id_samples"] == [1]
    assert health["ambiguous_samples"] == ["thirdkey"]


def test_dsp_catalog_diagnostics_render_only_bounded_examples():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "dsp_catalog_health.duplicate_numeric_ids" in page
    assert "dsp_catalog_health.ambiguous_samples[:5]" in page
    assert "dsp_catalog_health.duplicate_id_samples[:5]" in page


def test_dsp_numeric_id_collision_prevents_false_clean_identity(tmp_path: Path):
    source = tmp_path / "scripts" / "globals" / "keyitems.lua"
    source.parent.mkdir(parents=True)
    source.write_text("FIRST_KEY = 88;\nSECOND_KEY = 88;\n", encoding="utf-8")
    first = resolve_dsp_key_item(tmp_path, "First Key")
    second = resolve_dsp_key_item(tmp_path, "Second Key")
    assert first["status"] == "ambiguous" and first["symbol"] is None
    assert second["status"] == "ambiguous" and second["symbol"] is None
    assert first["conflicting_symbols"] == ["SECOND_KEY"]


def test_dsp_enum_labels_use_source_constants_without_invented_tpz_namespace():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert '{% if primary_dsp %}{{ rd.id_match }}{% else %}xi.keyItem.{{ rd.id_match }}{% endif %}' in page
    assert '{% if primary_dsp %}{{ rd.name_match[1] }}{% else %}xi.keyItem.{{ rd.name_match[1] }}{% endif %}' in page
    assert '"tpz.ki" if primary_dsp' not in page


def test_dsp_mapping_reason_is_visible_without_guessing_aliases():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    browse = host.split("def keyitems(request: Request", 1)[1].split('@app.get("/keyitems/lua-references.json")', 1)[0]
    assert '"reason": reason' in browse
    assert '"identity_source": match.get("source_path")' in browse
    assert "numeric IDs differ" in browse
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "rd.reason" in page
    assert "rd.identity_source" in page


def test_dsp_matching_does_not_infer_unverified_near_name_alias(tmp_path: Path):
    source = tmp_path / "scripts" / "globals" / "keyitems.lua"
    source.parent.mkdir(parents=True)
    source.write_text("LETTER_TO_THE_CONSULS_SANDORIA = 5;\n", encoding="utf-8")
    assert resolve_dsp_key_item(tmp_path, "Letter to the Consuls San d'Oria")["status"] == "missing"
    assert resolve_dsp_key_item(tmp_path, "Letter to the Consuls Sandoria")["status"] == "name_verified"
