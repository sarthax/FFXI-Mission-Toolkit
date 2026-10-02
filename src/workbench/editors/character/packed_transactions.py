"""Guarded packed-BLOB editing for Character Editor.

Only explicitly supported packed fields are writable. Every write requires an offline character,
an exact lineage/layout match, a preview, and a transaction-time byte-for-byte stale-data check.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from .packed_codecs import (
    BITSET_BLOB_SIZES,
    BITSET_MEANINGFUL_BITS,
    BLUE_SPELL_ID_OFFSET,
    BLUE_SPELL_SLOT_COUNT,
    KEY_ITEM_BITS_PER_TABLE,
    KEY_ITEM_SET_BYTES,
    KEY_ITEM_TABLE_BYTES,
    KEY_ITEM_TABLE_COUNTS,
    MISSION_AREA_COUNT,
    MISSION_RECORD_SIZES,
    QUEST_AREA_COUNT,
    QUEST_RECORD_BYTES,
    QUEST_SET_BYTES,
    PackedCodecError,
    decode_assaults,
    decode_blue_spells,
    decode_campaign,
    decode_character_bitset,
    decode_key_items,
    decode_missions,
    decode_quests,
)
from .schema import CharacterSchema, discover_character_schema
from .session_state import detect_online_state


_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}
_CAPABILITY_COLUMN = {
    "missions": "missions",
    "quests": "quests",
    "assaults": "assault",
    "campaign": "campaign",
    "key_items": "keyitems",
    "blue_spells": "set_blue_spells",
    "abilities": "abilities",
    "weaponskills": "weaponskills",
    "titles": "titles",
    "visited_zones": "zones",
}


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


def _quest_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Toggle exactly one current/accepted or completed quest bit."""
    decode_quests(blob, family)
    area_id = int(operation.get("area_id", -1))
    quest_id = int(operation.get("quest_id", -1))
    state = str(operation.get("state", "")).strip().lower()
    if not 0 <= area_id < QUEST_AREA_COUNT:
        raise ValueError(f"area_id must be between 0 and {QUEST_AREA_COUNT - 1}")
    if not 0 <= quest_id < QUEST_SET_BYTES * 8:
        raise ValueError("quest_id must be between 0 and 255")
    if state not in {"current", "completed"}:
        raise ValueError("state must be either 'current' or 'completed'")
    if "enabled" not in operation:
        raise ValueError("enabled must be supplied for a quest flag edit")

    start = area_id * QUEST_RECORD_BYTES
    set_offset = 0 if state == "current" else QUEST_SET_BYTES
    byte_offset = start + set_offset + quest_id // 8
    mask = 1 << (quest_id % 8)
    before_enabled = bool(blob[byte_offset] & mask)
    data = bytearray(blob)
    if bool(operation["enabled"]):
        data[byte_offset] |= mask
    else:
        data[byte_offset] &= ~mask
    after_blob = bytes(data)
    decoded_after = decode_quests(after_blob, family)
    return (
        after_blob,
        {"area_id": area_id, "quest_id": quest_id, "state": state, "enabled": before_enabled},
        {
            "area_id": area_id,
            "quest_id": quest_id,
            "state": state,
            "enabled": quest_id in (
                decoded_after["areas"][area_id]["current_ids"]
                if state == "current"
                else decoded_after["areas"][area_id]["completed_ids"]
            ),
        },
    )


def _assault_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Edit current Assault ID and/or one completion flag in the verified 130-byte layout."""
    decoded_before = decode_assaults(blob, family)
    data = bytearray(blob)
    before: dict[str, Any] = {"current": decoded_before["current"]}

    if "current" in operation and operation["current"] is not None:
        current = int(operation["current"])
        if not 0 <= current <= 0xFFFF:
            raise ValueError("current Assault ID must be between 0 and 65535")
        data[0:2] = current.to_bytes(2, "little")

    completed_id = operation.get("completed_id")
    if completed_id is not None:
        completed_id = int(completed_id)
        if not 0 <= completed_id < 128:
            raise ValueError("completed_id must be between 0 and 127")
        if "completed" not in operation:
            raise ValueError("completed must be supplied when completed_id is supplied")
        before["completed_id"] = completed_id
        before["completed"] = completed_id in decoded_before["completed_ids"]
        data[2 + completed_id] = 1 if bool(operation["completed"]) else 0

    if "current" not in operation and completed_id is None:
        raise ValueError("At least one of current or completed_id must be supplied")

    after_blob = bytes(data)
    decoded_after = decode_assaults(after_blob, family)
    after: dict[str, Any] = {"current": decoded_after["current"]}
    if completed_id is not None:
        after["completed_id"] = completed_id
        after["completed"] = completed_id in decoded_after["completed_ids"]
    return after_blob, before, after


def _campaign_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Edit current Campaign ID and/or one completion flag in the verified 514-byte layout."""
    decoded_before = decode_campaign(blob, family)
    data = bytearray(blob)
    before: dict[str, Any] = {"current": decoded_before["current"]}

    if "current" in operation and operation["current"] is not None:
        current = int(operation["current"])
        if not 0 <= current <= 0xFFFF:
            raise ValueError("current Campaign ID must be between 0 and 65535")
        data[0:2] = current.to_bytes(2, "little")

    completed_id = operation.get("completed_id")
    if completed_id is not None:
        completed_id = int(completed_id)
        if not 0 <= completed_id < 512:
            raise ValueError("completed_id must be between 0 and 511")
        if "completed" not in operation:
            raise ValueError("completed must be supplied when completed_id is supplied")
        before["completed_id"] = completed_id
        before["completed"] = completed_id in decoded_before["completed_ids"]
        data[2 + completed_id] = 1 if bool(operation["completed"]) else 0

    if "current" not in operation and completed_id is None:
        raise ValueError("At least one of current or completed_id must be supplied")

    after_blob = bytes(data)
    decoded_after = decode_campaign(after_blob, family)
    after: dict[str, Any] = {"current": decoded_after["current"]}
    if completed_id is not None:
        after["completed_id"] = completed_id
        after["completed"] = completed_id in decoded_after["completed_ids"]
    return after_blob, before, after


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
    decode_key_items(blob, family)
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


def _blue_spell_edit(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Replace or clear exactly one verified set-blue-spell slot."""
    decoded_before = decode_blue_spells(blob, family)
    slot = int(operation.get("slot", -1))
    if not 0 <= slot < BLUE_SPELL_SLOT_COUNT:
        raise ValueError(f"slot must be between 0 and {BLUE_SPELL_SLOT_COUNT - 1}")
    if "spell_id" not in operation:
        raise ValueError("spell_id must be supplied for a blue spell slot edit")

    raw_spell_id = operation.get("spell_id")
    if raw_spell_id in (None, 0, ""):
        stored_value = 0
    else:
        spell_id = int(raw_spell_id)
        minimum = BLUE_SPELL_ID_OFFSET + 1
        maximum = BLUE_SPELL_ID_OFFSET + 0xFF
        if not minimum <= spell_id <= maximum:
            raise ValueError(f"spell_id must be 0/None to clear or between {minimum} and {maximum}")
        stored_value = spell_id - BLUE_SPELL_ID_OFFSET

    data = bytearray(blob)
    data[slot] = stored_value
    after_blob = bytes(data)
    decoded_after = decode_blue_spells(after_blob, family)
    return after_blob, decoded_before["slots"][slot], decoded_after["slots"][slot]


def _character_bitset_edit(
    blob: bytes,
    family: str,
    capability: str,
    operation: dict[str, Any],
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Toggle exactly one verified bit in abilities/weaponskills/titles/visited-zones state."""
    decode_character_bitset(capability, blob, family)
    bit_id = int(operation.get("bit_id", -1))
    maximum = BITSET_MEANINGFUL_BITS[capability][family] - 1
    if not 0 <= bit_id <= maximum:
        raise ValueError(f"bit_id must be between 0 and {maximum} for {family} {capability}")
    if "enabled" not in operation:
        raise ValueError("enabled must be supplied for a character bitset edit")

    offset = bit_id // 8
    mask = 1 << (bit_id % 8)
    before_enabled = bool(blob[offset] & mask)
    data = bytearray(blob)
    if bool(operation["enabled"]):
        data[offset] |= mask
    else:
        data[offset] &= ~mask
    after_blob = bytes(data)
    decode_character_bitset(capability, after_blob, family)
    after_enabled = bool(after_blob[offset] & mask)
    return (
        after_blob,
        {"bit_id": bit_id, "enabled": before_enabled},
        {"bit_id": bit_id, "enabled": after_enabled},
    )


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
            elif capability == "quests":
                after_blob, before, after = _quest_edit(before_blob, family, operation)
            elif capability == "assaults":
                after_blob, before, after = _assault_edit(before_blob, family, operation)
            elif capability == "campaign":
                after_blob, before, after = _campaign_edit(before_blob, family, operation)
            elif capability == "key_items":
                after_blob, before, after = _key_item_edit(before_blob, family, operation)
            elif capability == "blue_spells":
                after_blob, before, after = _blue_spell_edit(before_blob, family, operation)
            elif capability in BITSET_BLOB_SIZES:
                after_blob, before, after = _character_bitset_edit(before_blob, family, capability, operation)
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
