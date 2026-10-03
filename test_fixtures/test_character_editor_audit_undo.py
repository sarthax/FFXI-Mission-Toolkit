from __future__ import annotations

from pathlib import Path

from workbench.editors.character.audit import _decode, _encode
from workbench.editors.character.audit_undo import build_undo_plan

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src" / "workbench" / "editors" / "character"


def test_audit_binary_roundtrip_supports_restore_payloads():
    payload = {"blob": bytes(range(16)), "nested": {"extra": memoryview(b"\x01\x02")}}
    restored = _decode(_encode(payload))
    assert restored["blob"] == bytes(range(16))
    assert restored["nested"]["extra"] == b"\x01\x02"


def test_missing_event_is_blocked_without_database_access():
    class NoDatabaseAccess:
        def cursor(self):
            raise AssertionError("missing audit event should not touch the database")

    plan = build_undo_plan(NoDatabaseAccess(), event_id="does-not-exist", adapter_family="lsb")
    assert plan.ready is False
    assert any(issue.code == "event_missing" for issue in plan.issues)


def test_undo_module_has_operation_specific_stale_state_guards():
    text = (BASE / "audit_undo.py").read_text(encoding="utf-8")
    assert "character_online" in text
    assert "online_state_unknown" in text
    assert "adapter_mismatch" in text
    assert "already_undone" in text
    assert "after_state_drift" in text
    assert "restore_slot_occupied" in text
    assert "item_equipped" in text
    assert "inventory.add" in text
    assert "inventory.remove" in text
    assert "inventory.move" in text
    assert "spell." in text
    assert "blacklist." in text
    assert 'operation == "scalar.update"' in text
    assert 'operation.startswith("packed.")' in text
    assert 'operation=f"undo.{plan.operation}"' in text
    assert "undo_supported=False" in text


def test_lsb_admin_undo_dispatch_preserves_generic_undo_routes():
    audit_gui = (BASE / "audit_gui.py").read_text(encoding="utf-8")
    lsb_undo = (BASE / "lsb_admin_undo.py").read_text(encoding="utf-8")
    assert "build_lsb_admin_undo_plan" in audit_gui
    assert "apply_lsb_admin_undo" in audit_gui
    assert '== "lsb_admin.update"' in audit_gui
    assert "build_undo_plan" in audit_gui and "apply_undo" in audit_gui
    assert "after_state_drift" in lsb_undo
    assert "already_undone" in lsb_undo
    assert "_restore_lsb_admin" in lsb_undo
    assert 'operation="undo.lsb_admin.update"' in lsb_undo


def test_audit_history_api_is_compact_and_registers_guarded_undo_routes():
    audit_gui = (BASE / "audit_gui.py").read_text(encoding="utf-8")
    gui = (BASE / "gui.py").read_text(encoding="utf-8")
    assert 'router.get("/characters/{char_id}/audit.json")' in audit_gui
    assert 'router.post("/characters/{char_id}/audit/{event_id}/undo/preview")' in audit_gui
    assert 'router.post("/characters/{char_id}/audit/{event_id}/undo/apply")' in audit_gui
    assert '"before"' not in audit_gui.split("def _summary", 1)[1].split("def _undo_preview", 1)[0]
    assert '"after"' not in audit_gui.split("def _summary", 1)[1].split("def _undo_preview", 1)[0]
    assert "from .audit_gui import router as audit_router" in gui
    assert "router.include_router(audit_router)" in gui


def test_audit_history_ui_is_advanced_offline_preview_confirm_flow():
    script = (ROOT / "gui" / "static" / "character_editor_audit.js").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    assert "key === 'advanced'" in script
    assert "editableOnline()" in script
    assert "/undo/preview" in script
    assert "/undo/apply" in script
    assert "approved:true" in script
    assert "Already restored by a later audit event" in script
    assert "character_editor_audit.js" in template


if __name__ == "__main__":
    test_audit_binary_roundtrip_supports_restore_payloads()
    test_missing_event_is_blocked_without_database_access()
    test_undo_module_has_operation_specific_stale_state_guards()
    test_lsb_admin_undo_dispatch_preserves_generic_undo_routes()
    test_audit_history_api_is_compact_and_registers_guarded_undo_routes()
    test_audit_history_ui_is_advanced_offline_preview_confirm_flow()
