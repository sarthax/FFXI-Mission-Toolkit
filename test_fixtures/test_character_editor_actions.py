from workbench.editors.character.actions import AddItemRequest, preview_add_item


def test_add_item_preview_blocks_unverified_adapter():
    preview = preview_add_item(
        AddItemRequest(char_id=10, item_id=1234, quantity=1),
        adapter_family="lsb",
        inventory_supported=True,
        character_found=True,
        character_online=False,
        item_known=True,
        stack_limit=1,
        destination_known=True,
        adapter_write_verified=False,
    )
    assert preview.action == "add_item"
    assert preview.write_ready is False
    assert any(w.code == "adapter_write_unverified" and w.blocking for w in preview.warnings)


def test_add_item_preview_can_be_ready_when_all_guards_pass():
    preview = preview_add_item(
        AddItemRequest(char_id=10, item_id=1234, quantity=12, container=0, slot=5, source="item_browser"),
        adapter_family="topaz",
        inventory_supported=True,
        character_found=True,
        character_online=False,
        item_known=True,
        stack_limit=99,
        destination_known=True,
        adapter_write_verified=True,
    )
    assert preview.write_ready is True
    assert preview.payload["source"] == "item_browser"
    assert preview.payload["container"] == 0
    assert preview.payload["slot"] == 5


def test_add_item_preview_blocks_online_character_and_bad_stack():
    preview = preview_add_item(
        AddItemRequest(char_id=22, item_id=55, quantity=100),
        adapter_family="dsp",
        inventory_supported=True,
        character_found=True,
        character_online=True,
        item_known=True,
        stack_limit=12,
        destination_known=True,
        adapter_write_verified=True,
    )
    codes = {w.code for w in preview.warnings if w.blocking}
    assert "character_online" in codes
    assert "stack_limit_exceeded" in codes
    assert preview.write_ready is False
