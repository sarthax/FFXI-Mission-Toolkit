"""Key Items Lua inspector integration contracts (host + template)."""
from pathlib import Path


def test_key_item_lua_route_is_read_only_and_identity_guarded():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    section = host.split('@app.get("/keyitems/lua-references.json")', 1)[1].split("ZONE_BROWSE_PAGE_SIZE", 1)[0]
    assert "def keyitems_lua_references(" in section
    assert 'if lineage not in {"lsb", "topaz", "dsp"}' in section
    assert "resolve_keyitem_readiness(" in section
    assert 'status not in {"clean", "drifted"}' in section
    assert "discover_key_item_references(" in section
    assert "max_matches=200" in section
    assert "INSERT " not in section and "UPDATE " not in section and "DELETE " not in section


def test_key_item_inspector_renders_source_evidence_safely():
    template = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'id="ki-lineage"' in template
    assert "/keyitems/lua-references.json?" in template
    assert "results.replaceChildren(list)" in template
    assert "excerpt.textContent =" in template
    assert "location.textContent =" in template
    assert "generation !== luaGeneration" in template
    assert "selectedRecord.id" in template


def test_key_item_lua_inspector_operation_filters_and_copy_paths():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'id="ki-lua-operation"' in page
    assert "displayLuaReferences()" in page
    assert "ref.operation === selected" in page
    assert "Copy location" in page
    assert "copyValue(location.textContent)" in page


def test_lua_reference_rollups_and_limitations_are_presented_safely():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'id="ki-lua-summary"' in page
    assert 'id="ki-lua-limitations-list"' in page
    assert "data.operation_counts || {}" in page
    assert "line.textContent = String(message)" in page
    assert "limitations.length === 0" in page
    assert "generation !== luaGeneration" in page
