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

    assert "def save_item_atomic(item_id, tables, effects=None, comment=" in item_edit
    assert 'bid = _save_backup(f"atomic edit item {item_id}"' in item_edit
    assert "dat.validate_client_patch(item_id, client_fields)" in item_edit
    assert "client_report = dat.patch_client_item(item_id, client_fields)" in item_edit

    # Exact client-record snapshots make create/delete/edit undo-redo faithful.
    assert "def capture_client_record(item_id: int)" in item_dat
    assert "def restore_client_record(snapshot: dict)" in item_dat
    assert "previous_record_hex" in item_dat
    assert 'client_snapshot="auto"' in item_edit
    assert '"client_record": client_snapshot' in item_edit
    assert "saved_client = b.get(\"client_record\")" in item_edit
    assert "client_report = dat.restore_client_record(saved_client)" in item_edit
    assert '"item_exists": item_exists' in item_edit
    assert "itemUndoStack.push({itemId:j.item_id,backup:j.backup,label:'create item'})" in template
    assert "itemUndoStack.push({itemId:deletedId,backup:j.backup,label:'delete item'})" in template
    assert 'id="itemSessionHistory"' in template

    # Clone/create preview and atomic effect copy.
    assert 'id="cloneCurrentBtn"' in template
    assert 'id="cloneEffectScope"' in template
    assert "async function cloneCurrentItem()" in template
    assert "def preview_free_slot(cat_name: str)" in item_dat
    assert '@app.get("/itemedit/create-preview.json")' in gui
    assert "CURRENT CANDIDATE (not reserved; revalidated at Save)" in template
    assert "effects,comment" in template

    # Persistent authority / target status.
    assert 'id="itemStatusBar"' in template
    assert "LIVE CLIENT WRITE" in template
    assert "XI-PIVOT" in template
    assert 'id="datLatestBackup"' in template
    assert "async function refreshLatestDatBackup" in template

    # Active-target vs pristine DAT comparison.
    assert "PRISTINE_COMPARE_FIELDS" in item_dat
    assert "def compare_client_record_to_pristine(item_id: int)" in item_dat
    assert '@app.get("/itemedit/{item_id}/dat-pristine-diff.json")' in gui
    assert 'id="datPristineDiff"' in template
    assert "async function refreshPristineDiff()" in template
    assert "Changed from pristine (" in template

    # Exact snapshots remain bound to the authority they were captured from.
    assert "def capture_client_record(item_id: int, target: str | None = None)" in item_dat
    assert '"target_existed": target_existed' in item_dat
    assert "target = snapshot.get(\"target\", dat_target())" in item_dat
    assert "restore_target = saved_client.get(\"target\") if saved_client else None" in item_edit

    # Explicit per-field server/client reconciliation.
    assert "RECONCILE_SERVER_FIELDS" in item_edit
    assert "def reconcile_item(item_id, field, direction, comment=" in item_edit
    assert "field not in RECONCILE_SERVER_FIELDS" in item_edit
    assert '@app.post("/itemedit/reconcile")' in gui
    assert "Use Server" in template and "Use Client" in template
    assert "structural mismatch · reconcile manually" in template
    assert "async function reconcileField(field,direction)" in template
    assert "label:'reconcile '+field" in template

    # Richer search grid and recent navigation.
    assert "def search(q, category=\"\", min_level=-1, max_level=-1, job=-1, skill=-1, client_state=\"\", limit=200):" in item_edit
    assert "server-only" in item_edit and "mismatch" in item_edit and "synced" in item_edit
    assert 'id="searchMinLevel"' in template
    assert 'id="searchMaxLevel"' in template
    assert 'id="searchJob"' in template
    assert 'id="searchSkill"' in template
    assert 'id="searchClientState"' in template
    assert 'id="searchSort"' in template and 'id="searchDir"' in template
    assert "function renderSearchResults()" in template
    assert "let recentItems=[];" in template
    assert "async function navigateRecent(delta)" in template
    assert '@app.get("/itemedit/search.json")' in gui
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
    assert "def validate_item_changes(item_id, tables, effects=None):" in item_edit
    assert "MISSING_BASIC" in item_edit
    assert "WEAPON_WITHOUT_EQUIPMENT" in item_edit
    assert "UNKNOWN_MASK_BITS" in item_edit
    assert '@app.post("/itemedit/validate")' in gui
    assert "Save blocked by validation errors." in template
    assert "Validation warnings:" in template


    # Staged mods / pet mods / latents are part of the same dirty/save transaction.
    assert "let loadedEffects={mods:[],pet_mods:[],latents:[]};" in template
    assert "function effectsDirty()" in template
    assert "function stagedEffectPayload()" in template
    assert "staged; saved with Save Item" in template
    assert "data-stage-mod" in template
    assert "data-stage-petmod" in template
    assert "stageAddLatent" in template
    assert "body:JSON.stringify({item_id:currentItemId,tables,effects,comment})" in template
    assert "effect_changes" in item_edit
    assert "def _normalize_effects(effects):" in item_edit
    assert "def _effect_changes(cu, item_id, desired):" in item_edit
    assert "duplicate item_mods modId" in item_edit
    assert "duplicate item_mods_pet key" in item_edit
    assert "duplicate item_latents key" in item_edit
    assert "UNKNOWN_MOD_ID" in item_edit
    assert "UNKNOWN_PET_TYPE" in item_edit
    assert "UNKNOWN_LATENT_ID" in item_edit

    # Restore keeps SQL and decoded client DAT overlaps synchronized for undo/redo.
    assert 'def restore(bid):' in item_edit
    assert "client_fields.update(_map_to_client_fields(t, row))" in item_edit
    assert "client_report = dat.patch_client_item(item_id, client_fields)" in item_edit


if __name__ == "__main__":
    main()
