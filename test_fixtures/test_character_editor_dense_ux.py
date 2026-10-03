from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "gui" / "templates" / "character_editor_progression.html"
DENSE = ROOT / "gui" / "static" / "character_editor_dense_ux.js"
MODES = ROOT / "gui" / "static" / "character_editor_dense_modes.js"


def test_dense_ux_load_order_wraps_base_before_semantic_editors_and_modes_last():
    text = TEMPLATE.read_text(encoding="utf-8")
    dense = text.index('/static/character_editor_dense_ux.js')
    progression = text.index('/static/character_editor_progression.js')
    bitsets = text.index('/static/character_editor_bitset_edit.js')
    modes = text.index('/static/character_editor_dense_modes.js')
    assert dense < progression < bitsets < modes


def test_dense_ux_compacts_scalar_and_inventory_surfaces():
    text = DENSE.read_text(encoding="utf-8")
    assert 'ce-dense-field-grid' in text
    assert "denseTables = new Set(['chars','char_jobs'" in text
    assert 'ce-inventory-grid' in text
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in text
    assert 'width:22px;height:22px' in text
    assert 'max-height:285px' in text


def test_decoded_packed_state_is_semantic_first_and_raw_storage_is_advanced():
    text = DENSE.read_text(encoding="utf-8")
    assert 'Advanced physical storage' in text
    assert 'semantic editor available' in text
    assert 'Decoded state is presented by the purpose-built editor above.' in text
    assert "pill('codec required'" not in text


def test_current_state_modes_default_key_items_bitsets_and_spells_to_owned_or_learned():
    text = MODES.read_text(encoding="utf-8")
    assert 'ensureOwnedKeyItemRows' in text
    assert "input[data-kind=\"owned\"]" in text
    assert "input[data-bit-id]" in text
    assert "learnedOnly.checked = true" in text
    assert "Browse all" in text
    assert "Current only" in text


def test_current_key_item_mode_preserves_owned_ids_outside_catalog_page_cap():
    text = MODES.read_text(encoding="utf-8")
    assert 'for (const id of owned)' in text
    assert 'if (present.has(id)) continue' in text
    assert "list.appendChild(node)" in text
    assert "capability, operation, expected_before_sha256" in text
