import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    template = (ROOT / "gui" / "templates" / "itemedit.html").read_text(encoding="utf-8")
    item_edit = (ROOT / "src" / "workbench" / "editors" / "items" / "_editor_impl.py").read_text(encoding="utf-8")
    item_dat = (ROOT / "src" / "workbench" / "editors" / "items" / "_dat_tools_impl.py").read_text(encoding="utf-8")
    gui = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")

    assert 'id="dirtySummary"' in template
    assert 'id="saveAllBtn"' in template
    assert "function collectCurrentTables()" in template
    assert "function changedTables()" in template
    assert "UNSAVED · " in template
    assert "Discard unsaved Item Editor changes?" in template
    assert "beforeunload" in template

    assert "def save_item_atomic(item_id, tables, effects=None, comment=" in item_edit
    assert re.search(r'bid = _save_backup\(\s*f"atomic edit item \{item_id\}"', item_edit)
    assert "dat.validate_client_patch(item_id, client_fields)" in item_edit
    assert "client_report = dat.patch_client_item(item_id, client_fields)" in item_edit

    # Effect staging tools: copy from another item and batch multi-add without immediate writes.
    assert 'id="effectStagingTools"' in template
    assert 'id="copyEffectsSource"' in template
    assert 'id="batchEffectsText"' in template
    assert "async function copyEffectsFromItem()" in template
    assert "function parseBatchEffects()" in template
    assert "mergeEffectRows(kind, rows)" in template
    assert "clone-template.json?item_id=" in template
    assert "duplicate key in batch" in template

    # DAT/ID slot browser uses real server + DAT occupancy and only verified reservation rules.
    assert "def browse_slots(cat_name: str, offset: int = 0, limit: int = 200, state: str = '')" in item_dat
    assert "'used-both'" in item_dat and "'server-only'" in item_dat and "'dat-only'" in item_dat and "'free'" in item_dat
    assert "reserved = item_id == 0" in item_dat
    assert '@app.get("/itemedit/slot-browser.json")' in gui
    assert 'id="slotBrowser"' in template
    assert "async function refreshSlotBrowser()" in template

    # Live <-> Xi-Pivot comparison/copy operates on this item record only.
    assert "def compare_live_pivot_record(item_id: int) -> dict:" in item_dat
    assert "def copy_live_pivot_record(item_id: int, direction: str) -> dict:" in item_dat
    assert "backup_dat_snapshot(dest_path, en_rom)" in item_dat
    assert '@app.get("/itemedit/{item_id}/live-pivot-diff.json")' in gui
    assert '@app.post("/itemedit/live-pivot-copy")' in gui
    assert 'id="livePivotDiff"' in template
    assert "async function compareLivePivot()" in template
    assert "async function copyLivePivot(direction)" in template

    # Safe item-level DAT record restore from exact backup snapshots.
    assert "def restore_client_record_from_backup(bid, comment=" in item_edit
    assert '"has_client_record": bool(snap)' in item_edit
    assert '@app.post("/itemedit/restore-client-record")' in gui
    assert "data-restore-record" in template
    assert "async function restoreItemDatRecord(bid)" in template
    assert "Server SQL will not be changed" in template
    assert "label:'restore DAT record'" in template

    # Dependency/usage view distinguishes exact DB references from advisory source text.
    assert "def _indexed_item_usage(item_id: int, internal_name: str)" in item_edit
    assert '"catalog_relationship"' in item_edit
    assert '"graph_relationship"' in item_edit
    assert '"client_index"' in item_edit
    assert '"graph_reference_count"' in item_edit
    assert '"client_reference_count"' in item_edit
    assert "graph/catalog" in template
    assert "client-index references" in template
    assert "def item_usage(item_id: int, source_limit: int = 100) -> dict:" in item_edit
    assert "CONTENT_TABLE_HINTS" in item_edit
    assert '"database_exact"' in item_edit
    assert '"source_text"' in item_edit
    assert '"blocking_reference_count"' in item_edit
    assert "source_limit <= 0" in item_edit
    assert '@app.get("/itemedit/{item_id}/usage.json")' in gui
    assert 'id="itemUsagePanel"' in template
    assert "async function refreshItemUsage(includeSource=false)" in template
    assert "refreshItemUsage(false)" in template
    assert "refreshItemUsage(true)" in template
    assert "DEPENDENCY WARNING:" in template

    # Selected-item change history is item-scoped, metadata-aware, and restorable.
    assert "def list_item_history(item_id, limit=100):" in item_edit
    assert '"metadata": metadata or {}' in item_edit
    assert '"action_type": "edit"' in item_edit
    assert '"action_type": "create"' in item_edit
    assert '"action_type": "delete"' in item_edit
    assert '"action_type": "reconcile"' in item_edit
    assert '@app.get("/itemedit/{item_id}/history.json")' in gui
    assert 'id="selectedItemHistory"' in template
    assert "async function refreshSelectedItemHistory()" in template
    assert "async function restoreSelectedHistory(bid" in template
    assert "Current state will be backed up first." in template

    # Exact client-record snapshots make create/delete/edit undo-redo faithful.
    assert "def capture_client_record(item_id: int" in item_dat
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

    # Constrained batch editing is preview-first, whitelisted, atomic, and backup-backed.
    assert "BATCH_SAFE_FIELDS = dict(RECONCILE_SERVER_FIELDS)" in item_edit
    assert "def preview_batch_edit(item_ids, field, value):" in item_edit
    assert "def apply_batch_edit(item_ids, field, value, comment=\"\"):" in item_edit
    assert "def restore_batch_backup(bid, comment=\"\"):" in item_edit
    assert "bulk dual-authority edit is blocked" in item_edit
    assert '"kind": "batch"' in item_edit
    assert '@app.post("/itemedit/batch/preview")' in gui
    assert '@app.post("/itemedit/batch/apply")' in gui
    assert '@app.post("/itemedit/batch/restore")' in gui
    assert 'id="itemBatchEditor"' in template
    assert "async function previewItemBatch()" in template
    assert "async function applyItemBatch()" in template
    assert "Batch inputs changed after preview. Preview again." in template
    assert "async function restoreLastItemBatch()" in template
    assert "data-history-batch" in template

    # DAT-only discovery searches client records without requiring a server row.
    assert "def search_dat_only(q: str, category: str = \"\", limit: int = 200) -> list:" in item_dat
    assert 'client_state": "dat-only"' in item_dat
    assert 'if client_state == "dat-only":' in item_edit
    assert '<option value="dat-only">DAT-only</option>' in template
    assert 'id="datOnlyPreview"' in template
    assert "async function inspectDatOnlyItem(itemid)" in template
    assert "data-inspect-dat-only" in template

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


    # Full client Item DAT record inspector: embedded icon preview and source-backed fields.
    assert "FURNITURE_DAT = 'ROM/74/21.DAT'" in item_dat
    assert "def furniture_properties(item_id: int)" in item_dat
    assert "def item_record_layout_audit() -> dict:" in item_dat
    assert '"extra_tail_capacity"' in item_dat
    assert '@app.get("/itemedit/client-layout-audit.json")' in gui
    assert "Furniture FUD" in template
    assert 'id="clientLayoutAudit"' in template
    assert "async function refreshClientLayoutAudit()" in template
    assert "def client_record_inspector(item_id: int) -> dict:" in item_dat
    assert "def item_icon_png(item_id: int)" in item_dat
    assert "def bitmap_a_to_png(raw: bytes)" in item_dat
    assert "icon_sha256" in item_dat
    assert '"shield_size"' in item_dat and '"base_item_id"' in item_dat and '"element_charge"' in item_dat
    assert '@app.get("/itemedit/{item_id}/client-record.json")' in gui
    assert '@app.get("/itemedit/{item_id}/icon.png")' in gui
    assert 'id="clientRecordInspector"' in template
    assert 'id="clientItemIcon"' in template
    assert "async function refreshClientRecordInspector(itemid)" in template
    assert "await refreshClientRecordInspector(itemid)" in template
    assert "Only source-confirmed fields are named here" in item_dat

    # Editing/presentation QOL: mode switching, logical grouping, decoded summaries,
    # field help, and staged item-to-item field/effect comparison stay presentation-only.
    assert 'id="itemEditorMode"' in template
    assert "const FIELD_GROUPS =" in template
    assert "const BASIC_FIELDS =" in template
    assert "const FIELD_HELP =" in template
    assert "function applyEditorModeVisibility()" in template
    assert "el.style.display=(basic && !BASIC_FIELDS[table]?.has(field))?'none':'';" in template
    assert "if(wrap.id==='editorTables'){ addEditorCopyControls(wrap); applyEditorModeVisibility(); }" in template
    assert 'id="decodedSummary"' in template
    assert "function renderDecodedSummary(" in template
    assert 'id="compareItemId"' in template
    assert "async function compareCurrentItem()" in template
    assert "flattenItemForCompare" in template
    assert "effectCompareLabel" in template
    assert "function compareSideBySidePanel(title,leftObj,rightObj,leftLabel,rightLabel)" in template
    assert "function flattenDatRecord(rec)" in template
    assert "function effectMap(kind, rows)" in template
    assert "SQL fields" in template
    assert "Client DAT" in template
    assert "Item mods" in template
    assert "Pet mods" in template
    assert "Latents" in template
    assert "SQL + client DAT + mods + pet mods + latents" in template
    assert 'id="fieldClipboardStatus"' in template
    assert "let itemFieldClipboard=null;" in template
    assert "function copyEditorField(table,field)" in template
    assert "function pasteEditorField(table,field)" in template
    assert "paste is limited to the same field" in template
    assert "function copyEditorGroup(table,groupName)" in template
    assert "function pasteEditorGroup(table,groupName)" in template
    assert "paste is limited to the same logical group" in template

    # Source-backed modifier units/comments and latentParam semantics.
    assert "def mod_metadata(names=None) -> dict:" in item_dat
    assert "def latent_metadata(names=None) -> dict:" in item_dat
    assert "Topaz modifier.h enum comment" in item_dat
    assert "Topaz latent_effect.h enum comment" in item_dat
    assert "def mod_metadata():" in item_edit
    assert "def latent_metadata():" in item_edit
    assert '@app.get("/itemedit/modmeta.json")' in gui
    assert '@app.get("/itemedit/latentmeta.json")' in gui
    assert "let MOD_META = {};" in template
    assert "let LATENT_META = {};" in template
    assert "function modMetaLine(modId)" in template
    assert "function latentParamLine(latentId)" in template
    assert "source-backed modifier comments/units" in template
    assert "source-backed activation-condition and latentParam semantics" in template

    # Staged mods / pet mods / latents are part of the same dirty/save transaction.
    assert "let loadedEffects={mods:[],pet_mods:[],latents:[]};" in template
    assert "function effectsDirty()" in template
    assert "function stagedEffectPayload()" in template
    assert "staged until Save Item" in template
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
    assert "client_fields.update(_map_to_client_fields(table, fields))" in item_edit
    assert "client_report = dat.patch_client_item(item_id, client_fields)" in item_edit


def test_client_job_mask_shift():
    from workbench.editors.items import editor as item_edit
    # client DAT job masks leave bit 0 unused (WAR = bit 1); server masks put WAR at bit 0
    rows = {"item_basic": {}, "item_equipment": {"jobs": 2098561, "level": 1, "slot": 1}}
    assert not item_edit.compare_server_client(rows, {"jobs": 4197122, "level": 1, "slots": 1})["mismatches"]
    assert item_edit._map_to_client_fields("item_equipment", {"jobs": 2098561}) == {"jobs": 4197122}
    assert item_edit._client_jobs_to_server(4197122) == 2098561

if __name__ == "__main__":
    test_client_job_mask_shift()
    main()
