from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    template = (ROOT / "gui" / "templates" / "itemedit.html").read_text(encoding="utf-8")
    item_edit = (ROOT / "item_edit.py").read_text(encoding="utf-8")
    item_dat = (ROOT / "item_dat_tools.py").read_text(encoding="utf-8")
    gui = (ROOT / "gui_server.py").read_text(encoding="utf-8")

    assert 'id="dirtySummary"' in template
    assert 'id="saveAllBtn"' in template
    assert "function collectCurrentTables()" in template
    assert "function changedTables()" in template
    assert "UNSAVED · " in template
    assert "Discard unsaved Item Editor changes?" in template
    assert "beforeunload" in template

    assert "def save_item_atomic(item_id, tables, comment=" in item_edit
    assert 'bid = _save_backup(f"atomic edit item {item_id}"' in item_edit
    assert "dat.validate_client_patch(item_id, client_fields)" in item_edit
    assert "client_report = dat.patch_client_item(item_id, client_fields)" in item_edit
    assert 'backup_path = client_report.get("backup_path")' in item_edit
    assert "shutil.copy2(backup_path, dat_path)" in item_edit
    assert "def validate_client_patch(item_id: int, fields: dict)" in item_dat
    assert '@app.post("/itemedit/save-atomic")' in gui

    assert "const itemUndoStack = [], itemRedoStack = [];" in template
    assert "async function restoreItemHistory(source,target,verb)" in template
    assert "j.pre_restore_backup" in template
    assert "itemUndoBtn" in template and "itemRedoBtn" in template
    assert "ev.key.toLowerCase()==='z'" in template
    assert "ev.key.toLowerCase()==='y'" in template

    assert "def compare_server_client(rows, client):" in item_edit
    for field in ("item_type", "flags", "stack", "level", "jobs", "slots", "damage", "delay", "skill"):
        assert f"('{field}'" in item_edit
    assert "Server / client DAT mismatches" in template
    assert "all decoded overlapping fields match" in template

    assert "def validate_item_state(rows, client=None):" in item_edit
    assert "def validate_item_changes(item_id, tables):" in item_edit
    assert "MISSING_BASIC" in item_edit
    assert "WEAPON_WITHOUT_EQUIPMENT" in item_edit
    assert "UNKNOWN_MASK_BITS" in item_edit
    assert '@app.post("/itemedit/validate")' in gui
    assert "Save blocked by validation errors." in template
    assert "Validation warnings:" in template


if __name__ == "__main__":
    main()
