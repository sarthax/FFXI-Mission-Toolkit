"""Durable local audit history for Character Editor mutations.

Character Editor writes are direct database administration operations. Successful mutations
must leave enough local evidence to answer what changed and, when an operation supplies an exact
before-state snapshot, to support a later guarded restore workflow.

The journal is append-only JSONL under ``data/`` and binary values are encoded losslessly as
hex objects. Exact before-state payloads are also written to an individual backup JSON file so
a future undo implementation does not need to parse or rewrite the journal. Connection secrets
are never accepted as record fields by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
from typing import Any

from workbench.runtime.paths import DATA_ROOT

AUDIT_LOG_PATH = DATA_ROOT / "character_editor_audit.jsonl"
AUDIT_BACKUP_ROOT = DATA_ROOT / "character_editor_backups"

_SECRET_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "database_password", "sql_password", "session_key",
}


def _encode(value: Any) -> Any:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return {"__hex__": bytes(value).hex(), "__bytes__": len(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.lower() in _SECRET_KEYS:
                out[name] = "<redacted>"
            else:
                out[name] = _encode(item)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_encode(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if "__hex__" in value:
            return bytes.fromhex(str(value["__hex__"]))
        return {str(key): _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp_utc: str
    operation: str
    char_id: int
    adapter_family: str
    status: str
    target: dict[str, Any]
    before: Any
    after: Any
    metadata: dict[str, Any]
    backup_path: str | None
    undo_supported: bool

    def as_dict(self) -> dict[str, Any]:
        return _encode(asdict(self))


def _new_event_id() -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{now}-{secrets.token_hex(4)}"


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{secrets.token_hex(4)}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(_encode(payload), handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def append_audit_event(
    *,
    operation: str,
    char_id: int,
    adapter_family: str,
    target: dict[str, Any] | None = None,
    before: Any = None,
    after: Any = None,
    metadata: dict[str, Any] | None = None,
    status: str = "committed",
    undo_supported: bool = False,
) -> AuditEvent:
    """Persist one successful Character Editor mutation and optional exact before-state backup."""
    operation = str(operation or "").strip()
    if not operation:
        raise ValueError("operation is required")
    char_id = int(char_id)
    if char_id <= 0:
        raise ValueError("char_id must be positive")

    event_id = _new_event_id()
    backup_path: Path | None = None
    if before is not None:
        backup_path = AUDIT_BACKUP_ROOT / f"{event_id}.json"
        _write_json_atomic(
            backup_path,
            {
                "event_id": event_id,
                "operation": operation,
                "char_id": char_id,
                "adapter_family": str(adapter_family or "unknown"),
                "before": before,
            },
        )

    event = AuditEvent(
        event_id=event_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        operation=operation,
        char_id=char_id,
        adapter_family=str(adapter_family or "unknown"),
        status=str(status or "committed"),
        target=dict(target or {}),
        before=before,
        after=after,
        metadata=dict(metadata or {}),
        backup_path=str(backup_path.relative_to(DATA_ROOT)) if backup_path is not None else None,
        undo_supported=bool(undo_supported),
    )

    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with AUDIT_LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return event


def attach_committed_audit(
    result: dict[str, Any],
    *,
    operation: str,
    char_id: int,
    adapter_family: str,
    target: dict[str, Any] | None = None,
    before: Any = None,
    after: Any = None,
    metadata: dict[str, Any] | None = None,
    undo_supported: bool = False,
) -> dict[str, Any]:
    """Attach audit outcome to an already-committed mutation without ever raising.

    Database commit has already happened when this helper is called. Audit I/O therefore cannot
    be allowed to make callers believe the mutation rolled back. The returned result always
    preserves the committed status and carries either ``audit_event_id``/``audit_backup_path``
    or an explicit ``audit_error`` for operator follow-up.
    """
    out = dict(result)
    try:
        event = append_audit_event(
            operation=operation,
            char_id=char_id,
            adapter_family=adapter_family,
            target=target,
            before=before,
            after=after,
            metadata=metadata,
            status="committed",
            undo_supported=undo_supported,
        )
        out["audit_event_id"] = event.event_id
        out["audit_backup_path"] = event.backup_path
        out["audit_error"] = None
    except Exception as exc:
        out["audit_event_id"] = None
        out["audit_backup_path"] = None
        out["audit_error"] = f"{type(exc).__name__}: {exc}"
    return out


def read_audit_events(*, char_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Return newest audit records without mutating the append-only journal."""
    safe_limit = max(1, min(int(limit), 5000))
    if not AUDIT_LOG_PATH.exists():
        return []
    wanted = int(char_id) if char_id is not None else None
    rows: list[dict[str, Any]] = []
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if wanted is not None and int(row.get("char_id") or 0) != wanted:
                continue
            rows.append(row)
    return rows[-safe_limit:][::-1]


def get_audit_event(event_id: str) -> dict[str, Any] | None:
    wanted = str(event_id or "").strip()
    if not wanted or not AUDIT_LOG_PATH.exists():
        return None
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if str(row.get("event_id") or "") == wanted:
                return _decode(row)
    return None


def load_audit_backup(event: dict[str, Any]) -> Any:
    """Load the exact decoded before-state backup for an event when one exists."""
    rel = str(event.get("backup_path") or "").strip()
    if not rel:
        return event.get("before")
    path = (DATA_ROOT / rel).resolve()
    root = DATA_ROOT.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Audit backup path escapes data root") from exc
    if not path.is_file():
        raise FileNotFoundError(f"Audit backup is missing: {rel}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("event_id") or "") != str(event.get("event_id") or ""):
        raise RuntimeError("Audit backup event ID does not match journal event")
    return _decode(payload.get("before"))
