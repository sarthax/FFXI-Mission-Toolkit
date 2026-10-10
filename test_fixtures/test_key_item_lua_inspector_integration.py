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


def test_key_item_lua_references_link_to_feature_trace_safely():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "const fileName = parts[parts.length - 1] || path;" in page
    assert "new URLSearchParams({q: fileName})" in page
    assert "search.href = '/features/trace?'" in page
    assert "context.textContent = ' · ' + kind + ' · ' + fileName" in page
    assert "excerpt.textContent = String(ref.source_text || '')" in page
    assert "location.textContent = String(ref.source_path || '')" in page


def test_key_item_source_scope_is_derived_from_actual_script_path():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "const relations = [];" in page
    assert "const segment = path.match(" in page
    assert "(missions|quests|npcs|zones)" in page
    assert "segment[2]" in page
    assert "item.append(label, location, context, ...relations, copy, search, excerpt)" in page


def test_key_item_references_group_by_source_without_losing_evidence():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "const grouped = new Map();" in page
    assert "grouped.get(key).push(item);" in page
    assert "for (const [path, items] of grouped)" in page
    assert "heading.textContent = path + ' · ' + items.length + ' reference(s)';" in page
    assert "entries.append(...items);" in page
    assert "group.open = grouped.size <= 3;" in page


def test_key_item_lua_group_summary_shows_operation_breakdown():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "const counts = {require: 0, grant: 0, remove: 0};" in page
    assert "Object.prototype.hasOwnProperty.call(counts, ref.operation)" in page
    assert "const operations = Object.entries(counts)" in page
    assert "operation + ': ' + count" in page


def test_key_item_lua_group_cites_exact_line_numbers():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "new Set(scopedRefs.map(ref => Number(ref.source_line))" in page
    assert "Number.isInteger(line) && line > 0" in page
    assert "lines.join(', ')" in page
    assert "group.append(heading, citations, entries);" in page


def test_key_item_script_evidence_can_be_copied_with_exact_citations():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert "copyEvidence.textContent = 'Copy script evidence';" in page
    assert "const evidence = scopedRefs.map(ref => {" in page
    assert "String(ref.source_path || '') + ':' + String(ref.source_line || '')" in page
    assert "String(ref.source_text || '')" in page
    assert "group.append(heading, citations, copyEvidence, entries);" in page
