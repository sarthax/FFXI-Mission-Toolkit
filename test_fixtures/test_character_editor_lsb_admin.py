from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src" / "workbench" / "editors" / "character"


def test_lsb_admin_writer_is_narrow_and_lineage_gated():
    text = (BASE / "lsb_admin_transactions.py").read_text(encoding="utf-8")
    assert '_FLAG_COLUMNS = {"gmModeEnabled", "gmHiddenEnabled", "muted", "rename"}' in text
    assert '"disconnecting"' in text  # required schema evidence, but not editable allowlist
    assert 'family != "lsb"' in text
    assert '"char_flags": _FLAG_COLUMNS' in text
    assert '"char_history": _HISTORY_COLUMNS' in text
    assert '"char_pet"' not in text
    assert '"char_effects"' not in text
    assert '"char_recast"' not in text


def test_lsb_admin_writer_rechecks_offline_and_stale_row_then_audits_after_commit():
    text = (BASE / "lsb_admin_transactions.py").read_text(encoding="utf-8")
    assert "detect_online_state" in text
    assert "state.online is True" in text
    assert "state.online is None" in text
    assert "current != plan.before" in text
    assert "connection.commit()" in text
    assert "attach_committed_audit" in text
    assert text.index("connection.commit()") < text.rindex("attach_committed_audit")
    assert 'operation="lsb_admin.update"' in text
    assert "undo_supported=True" in text


def test_lsb_admin_undo_is_lsb_only_stale_safe_and_restores_only_changed_fields():
    text = (BASE / "lsb_admin_undo.py").read_text(encoding="utf-8")
    assert 'operation != "lsb_admin.update"' in text
    assert 'event_family != "lsb" or current_family != "lsb"' in text
    assert "character_online" in text and "online_state_unknown" in text
    assert "schema_unverified" in text
    assert "after_state_drift" in text
    assert "_ALLOWED[table]" in text
    assert 'metadata") or {}).get("changes")' in text
    assert 'params = [plan.before.get(name) for name in changes] + [plan.char_id]' in text
    assert 'operation="undo.lsb_admin.update"' in text
    assert "undo_supported=False" in text


def test_lsb_admin_routes_require_preview_and_explicit_approval():
    text = (BASE / "audit_gui.py").read_text(encoding="utf-8")
    assert 'router.post("/characters/{char_id}/lsb-admin/preview")' in text
    assert 'router.post("/characters/{char_id}/lsb-admin/apply")' in text
    assert 'body.get("approved") is not True' in text
    assert 'expected_before = body.get("expected_before")' in text
    assert "Administrative state changed since preview" in text
    assert "build_lsb_admin_undo_plan" in text
    assert "apply_lsb_admin_undo" in text
    assert 'event.get("operation") or "") == "lsb_admin.update"' in text


def test_lsb_admin_ui_is_advanced_lsb_only_and_keeps_runtime_state_read_only():
    script = (ROOT / "gui" / "static" / "character_editor_lsb_admin.js").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    assert "key === 'advanced'" in script
    assert "adapter?.family" in script
    assert "!== 'lsb'" in script
    assert "disconnecting" in script
    assert "runtime/session state · read only" in script
    assert "status effects, recasts, pet IDs, and pet BLOB state remain read-only" in script
    assert "editableOnline()" in script
    assert "/lsb-admin/preview" in script
    assert "/lsb-admin/apply" in script
    assert "expected_before:preview.before" in script
    assert "character_editor_lsb_admin.js" in template


if __name__ == "__main__":
    test_lsb_admin_writer_is_narrow_and_lineage_gated()
    test_lsb_admin_writer_rechecks_offline_and_stale_row_then_audits_after_commit()
    test_lsb_admin_undo_is_lsb_only_stale_safe_and_restores_only_changed_fields()
    test_lsb_admin_routes_require_preview_and_explicit_approval()
    test_lsb_admin_ui_is_advanced_lsb_only_and_keeps_runtime_state_read_only()
