from __future__ import annotations

import json
from pathlib import Path
import tempfile

import workbench.editors.character.audit as audit


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old_data_root = audit.DATA_ROOT
        old_log = audit.AUDIT_LOG_PATH
        old_backups = audit.AUDIT_BACKUP_ROOT
        audit.DATA_ROOT = root
        audit.AUDIT_LOG_PATH = root / "character_editor_audit.jsonl"
        audit.AUDIT_BACKUP_ROOT = root / "character_editor_backups"
        try:
            event = audit.append_audit_event(
                operation="inventory.quantity",
                char_id=123,
                adapter_family="lsb",
                target={"location": 0, "slot": 1},
                before={"quantity": 1, "extra": bytes.fromhex("00ff"), "password": "do-not-log"},
                after={"quantity": 2},
                metadata={"source": "character-editor", "token": "secret-token"},
                undo_supported=True,
            )
            assert audit.AUDIT_LOG_PATH.exists()
            assert event.backup_path is not None
            backup = audit.DATA_ROOT / event.backup_path
            assert backup.exists()

            row = json.loads(audit.AUDIT_LOG_PATH.read_text(encoding="utf-8").strip())
            assert row["operation"] == "inventory.quantity"
            assert row["char_id"] == 123
            assert row["before"]["extra"] == {"__bytes__": 2, "__hex__": "00ff"}
            assert row["before"]["password"] == "<redacted>"
            assert row["metadata"]["token"] == "<redacted>"
            assert row["undo_supported"] is True

            rows = audit.read_audit_events(char_id=123, limit=10)
            assert len(rows) == 1
            assert rows[0]["event_id"] == event.event_id
            assert audit.read_audit_events(char_id=999, limit=10) == []
        finally:
            audit.DATA_ROOT = old_data_root
            audit.AUDIT_LOG_PATH = old_log
            audit.AUDIT_BACKUP_ROOT = old_backups


if __name__ == "__main__":
    main()
