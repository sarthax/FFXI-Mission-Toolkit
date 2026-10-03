from __future__ import annotations

from pathlib import Path

import workbench.editors.character.audit as audit

ROOT = Path(__file__).resolve().parents[1]


def test_audit_failure_does_not_hide_committed_database_result():
    original = audit.append_audit_event
    try:
        def fail(**kwargs):
            raise OSError("disk unavailable")

        audit.append_audit_event = fail
        result = audit.attach_committed_audit(
            {"status": "committed", "char_id": 1},
            operation="inventory.remove",
            char_id=1,
            adapter_family="lsb",
            before={"itemId": 4096},
            after=None,
        )
        assert result["status"] == "committed"
        assert result["audit_event_id"] is None
        assert result["audit_backup_path"] is None
        assert "disk unavailable" in result["audit_error"]
    finally:
        audit.append_audit_event = original


def test_row_write_paths_attach_durable_audit():
    files = {
        "inventory_management.py": "inventory.{plan.action}",
        "item_transactions.py": 'operation="inventory.add"',
        "spell_transactions.py": "spell.{plan.action}",
        "blacklist_transactions.py": "blacklist.{plan.action}",
    }
    base = ROOT / "src" / "workbench" / "editors" / "character"
    for name, marker in files.items():
        text = (base / name).read_text(encoding="utf-8")
        assert "attach_committed_audit" in text, name
        assert marker in text, name
        assert "connection.commit()" in text, name
        assert text.index("connection.commit()") < text.rindex("attach_committed_audit"), name
        assert "undo_supported=True" in text, name


def test_scalar_audit_preserves_full_before_and_after_rows():
    text = (ROOT / "src" / "workbench" / "editors" / "character" / "scalar_transactions.py").read_text(encoding="utf-8")
    assert 'operation="scalar.update"' in text
    assert "after = dict(plan.before or {})" in text
    assert "after.update(plan.changes)" in text
    assert 'target={"table": plan.table, "selector": dict(plan.selector)}' in text
    assert "before=plan.before" in text
    assert "after=after" in text
    assert "undo_supported=True" in text
    assert text.index("connection.commit()") < text.rindex("attach_committed_audit")


def test_packed_audit_preserves_raw_blobs_and_decoded_metadata():
    text = (ROOT / "src" / "workbench" / "editors" / "character" / "packed_transactions.py").read_text(encoding="utf-8")
    assert 'operation=f"packed.{plan.capability}"' in text
    assert 'before={"blob": plan.before_blob, "decoded": plan.before}' in text
    assert 'after={"blob": plan.after_blob, "decoded": plan.after}' in text
    assert 'target={"table": "chars", "column": plan.column, "capability": plan.capability}' in text
    assert "undo_supported=True" in text
    assert text.index("connection.commit()") < text.rindex("attach_committed_audit")


def test_eminence_reuses_packed_edit_plan_and_is_covered_by_packed_audit():
    text = (ROOT / "src" / "workbench" / "editors" / "character" / "eminence_transactions.py").read_text(encoding="utf-8")
    assert "from .packed_transactions import PackedEditPlan" in text
    assert "-> PackedEditPlan:" in text
    assert 'capability = "eminence"' in text


if __name__ == "__main__":
    test_audit_failure_does_not_hide_committed_database_result()
    test_row_write_paths_attach_durable_audit()
    test_scalar_audit_preserves_full_before_and_after_rows()
    test_packed_audit_preserves_raw_blobs_and_decoded_metadata()
    test_eminence_reuses_packed_edit_plan_and_is_covered_by_packed_audit()
