"""Guarded mission/key-item BLOB editing for Character Editor.

Only explicitly supported packed fields are writable.  Every write requires an offline character,
an exact lineage/layout match, a preview, and a transaction-time byte-for-byte stale-data check.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from .packed_codecs import (
    KEY_ITEM_BITS_PER_TABLE,
    KEY_ITEM_SET_BYTES,
    KEY_ITEM_TABLE_BYTES,
    KEY_ITEM_TABLE_COUNTS,
    MISSION_AREA_COUNT,
    MISSION_RECORD_SIZES,
    PackedCodecError,
    decode_key_items,
    decode_missions,
)
from .schema import CharacterSchema, discover_character_schema
from .session_state import detect_online_state


_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}
_CAPABILITY_COLUMN = {"missions": "missions", "key_items": "keyitems"}


@dataclass(frozen=True)
class PackedIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class PackedEditPlan:
    char_id: int
    capability: str
    column: str
    operation: dict[str, Any]
    before_blob: bytes | None
    after_blob: bytes | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    online: bool | None
    adapter_family: str
    issues: list[PackedIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.before_blob is not None
            and self.after_blob is not None
            and self.before_blob != self.after_blob
            and not any(issue.blocking for issue in self.issues)
        )

    def as_dict(self) -> dict[str, Any]:
        def digest(value: bytes | None) -> str | None:
            return sha256(value).hexdigest() if value is not None else None

        return {
            "char_id": self.char_id,
            "capability": self.capability,
            "column": self.column,
            "operation": dict(self.operation),
            "before": self.before,
            "after": self.after,
            "before_bytes": len(self.before_blob) if self.before_blob is not None else None,
            "after_bytes": len(self.after_blob) if self.after_blob is not None else None,
            "before_sha256": digest(self.before_blob),
            "after_sha256": digest(self.after_blob),
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(issue) for issue in self.issues],
            "ready": self.ready,
        }


def _family(value: str) -> str:
    return str(value or "unknown").strip().lower()


def _chars_blob(connection, schema: CharacterSchema, char_id: int, column: str) -> bytes | None:
    table = schema.table("chars")
    if table is None or table.character_key is None or column not in table.column_names:
        return None
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"SELECT `{column}` FROM `chars` WHERE `{table.character_key}` = %s LIMIT 1",
            (int(char_id),),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None
        value = row[0]
        if isinstance(value, bytes):
            return value
        if isinstance(value, (bytearray, memoryview)):
            return bytes(value)
        raise PackedCodecError(f"chars.{column} is not bytes-like")
    finally:
        cursor.close()


def _mission_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    decoded_before = decode_missions(blob, family)
    area_id = int(operation.get("area_id", -1))
    if not 0 <= area_id < MISSION_AREA_COUNT:
        raise ValueError(f"area_id must be between 0 and {MISSION_AREA_COUNT - 1}")

    record_size = MISSION_RECORD_SIZES[family]
    start = area_id * record_size
    data = bytearray(blob)

    if "current" in operation and operation["current"] is not None:
        current = int(operation["current"])
        if not 0 <= current <= 0xFFFF:
            raise ValueError("current mission ID must be between 0 and 65535")
        data[start : start + 2] = current.to_bytes(2, "little")

    cursor = start + 2
    if record_size == 70:
        if "status_upper" in operation and operation["status_upper"] is not None:
            status_upper = int(operation["status_upper"])
            if not 0 <= status_upper <= 0xFFFF:
                raise ValueError("status_upper must be between 0 and 65535")
            data[cursor : cursor + 2] = status_upper.to_bytes(2, "little")
        if "status_lower" in operation and operation["status_lower"] is not None:
            status_lower = int(operation["status_lower"])
            if not 0 <= status_lower <= 0xFFFF:
                raise ValueError("status_lower must be between 0 and 65535")
            data[cursor + 2 : cursor + 4] = status_lower.to_bytes(2, "little")
        cursor += 4
    elif operation.get("status_upper") is not None or operation.get("status_lower") is not None:
        raise ValueError("DSP mission layout does not contain status_upper/status_lower fields")

    if "completed_id" in operation and operation["completed_id"] is not None:
        completed_id = int(operation["completed_id"])
        if not 0 <= completed_id < 64:
            raise ValueError("completed_id must be between 0 and 63")
        if "completed" not in operation:
            raise ValueError("completed must be supplied when completed_id is supplied")
        data[cursor + completed_id] = 1 if bool(operation["completed"]) else 0

    after_blob = bytes(data)
    decoded_after = decode_missions(after_blob, family)
    return after_blob, decoded_before["areas"][area_id], decoded_after["areas"][area_id]


def _bit_value(blob: bytes, key_item_id: int, *, seen: bool) -> bool:
    table = key_item_id // KEY_ITEM_BITS_PER_TABLE
    bit = key_item_id % KEY_ITEM_BITS_PER_TABLE
    base = table * KEY_ITEM_TABLE_BYTES + (KEY_ITEM_SET_BYTES if seen else 0)
    return bool(blob[base + bit // 8] & (1 << (bit % 8)))


def _set_bit(data: bytearray, key_item_id: int, *, seen: bool, value: bool) -> None:
    table = key_item_id // KEY_ITEM_BITS_PER_TABLE
    bit = key_item_id % KEY_ITEM_BITS_PER_TABLE
    offset = table * KEY_ITEM_TABLE_BYTES + (KEY_ITEM_SET_BYTES if seen else 0) + bit // 8
    mask = 1 << (bit % 8)
    if value:
        data[offset] |= mask
    else:
        data[offset] &= ~mask


def _key_item_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    decode_key_items(blob, family)  # exact layout validation before mutation
    key_item_id = int(operation.get("key_item_id", -1))
    maximum = KEY_ITEM_TABLE_COUNTS[family] * KEY_ITEM_BITS_PER_TABLE - 1
    if not 0 <= key_item_id <= maximum:
        raise ValueError(f"key_item_id must be between 0 and {maximum} for {family}")
    if "owned" not in operation and "seen" not in operation:
        raise ValueError("At least one of owned or seen must be supplied")

    before = {
        "key_item_id": key_item_id,
        "owned": _bit_value(blob, key_item_id, seen=False),
        "seen": _bit_value(blob, key_item_id, seen=True),
    }
    data = bytearray(blob)
    if "owned" in operation and operation["owned"] is not None:
        _set_bit(data, key_item_id, seen=False, value=bool(operation["owned"]))
    if "seen" in operation and operation["seen"] is not None:
        _set_bit(data, key_item_id, seen=True, value=bool(operation["seen"]))
    after_blob = bytes(data)
    decode_key_items(after_blob, family)
    after = {
        "key_item_id": key_item_id,
        "owned": _bit_value(after_blob, key_item_id, seen=False),
        "seen": _bit_value(after_blob, key_item_id, seen=True),
    }
    return after_blob, before, after


def build_packed_edit_plan(
    connection,
    *,
    char_id: int,
    capability: str,
    operation: dict[str, Any] | None = None,
    adapter_family: str = "unknown",
) -> PackedEditPlan:
    char_id = int(char_id)
    capability = str(capability or "").strip()
    operation = dict(operation or {})
    family = _family(adapter_family)
    column = _CAPABILITY_COLUMN.get(capability, "")
    issues: list[PackedIssue] = []
    schema = discover_character_schema(connection)

    if family not in _VERIFIED_FAMILIES:
        issues.append(PackedIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for packed writes."))
    if not column:
        issues.append(PackedIssue("capability_not_enabled", f"Packed capability {capability!r} is not enabled for editing."))
    expected_location = (schema.packed_fields or {}).get(capability)
    if column and expected_location != f"chars.{column}":
        issues.append(
            PackedIssue(
                "packed_location_unverified",
                f"Expected {capability} at chars.{column}, found {expected_location or 'no recognized packed field'}.",
            )
        )

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(PackedIssue("character_online", "Character is online; packed character writes are blocked."))
    elif state.online is None:
        issues.append(PackedIssue("online_state_unknown", "Character online state could not be verified."))

    before_blob = _chars_blob(connection, schema, char_id, column) if column else None
    if before_blob is None and column:
        issues.append(PackedIssue("blob_missing", f"Character has no chars.{column} BLOB."))

    after_blob: bytes | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    if before_blob is not None and family in _VERIFIED_FAMILIES and column:
        try:
            if capability == "missions":
                after_blob, before, after = _mission_edit(before_blob, family, operation)
            elif capability == "key_items":
                after_blob, before, after = _key_item_edit(before_blob, family, operation)
        except (PackedCodecError, TypeError, ValueError) as exc:
            issues.append(PackedIssue("invalid_packed_edit", str(exc)))

    if before_blob is not None and after_blob == before_blob and not any(issue.blocking for issue in issues):
        issues.append(PackedIssue("no_change", "Requested packed-state edit does not change the stored value."))

    return PackedEditPlan(
        char_id=char_id,
        capability=capability,
        column=column,
        operation=operation,
        before_blob=before_blob,
        after_blob=after_blob,
        before=before,
        after=after,
        online=state.online,
        adapter_family=family,
        issues=issues,
    )


def apply_packed_edit(connection, plan: PackedEditPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply packed character changes")
    if not plan.ready:
        raise RuntimeError("Packed edit plan is not write-ready")

    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor()
            try:
                cursor.execute("START TRANSACTION")
            finally:
                cursor.close()

        schema = discover_character_schema(connection)
        state = detect_online_state(connection, schema, plan.char_id)
        if state.online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if (schema.packed_fields or {}).get(plan.capability) != f"chars.{plan.column}":
            raise RuntimeError("Packed field location changed since preview")
        current = _chars_blob(connection, schema, plan.char_id, plan.column)
        if current != plan.before_blob:
            raise RuntimeError("Packed character data changed since preview; rebuild the edit plan")

        table = schema.table("chars")
        if table is None or table.character_key is None:
            raise RuntimeError("chars table is no longer available")
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"UPDATE `chars` SET `{plan.column}` = %s WHERE `{table.character_key}` = %s LIMIT 1",
                (plan.after_blob, plan.char_id),
            )
            if getattr(cursor, "rowcount", 1) not in (0, 1):
                raise RuntimeError("Unexpected number of rows updated")
        finally:
            cursor.close()
        connection.commit()
        return {
            "status": "committed",
            "char_id": plan.char_id,
            "capability": plan.capability,
            "column": plan.column,
            "operation": dict(plan.operation),
            "before": plan.before,
            "after": plan.after,
            "after_sha256": sha256(plan.after_blob or b"").hexdigest(),
        }
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
