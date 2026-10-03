"""Guarded Records of Eminence edits using the shared packed transaction contract."""
from __future__ import annotations

from typing import Any

from .eminence_codec import (
    EMINENCE_ACTIVE_SLOTS,
    EMINENCE_COMPLETE_OFFSET,
    EMINENCE_PROGRESS_OFFSET,
    EminenceCodecError,
    decode_eminence,
)
from .packed_transactions import PackedEditPlan, PackedIssue, _chars_blob
from .schema import discover_character_schema
from .session_state import detect_online_state

_VERIFIED_FAMILIES = {"topaz", "lsb"}


def _edit_blob(blob: bytes, family: str, operation: dict[str, Any]) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    decoded_before = decode_eminence(blob, family)
    kind = str(operation.get("kind") or "").strip().lower()
    data = bytearray(blob)

    if kind == "active_slot":
        slot = int(operation.get("slot", -1))
        if not 0 <= slot < EMINENCE_ACTIVE_SLOTS:
            raise ValueError(f"slot must be between 0 and {EMINENCE_ACTIVE_SLOTS - 1}")
        if "record_id" not in operation or "progress" not in operation:
            raise ValueError("active_slot edits require both record_id and progress")
        record_id = int(operation.get("record_id"))
        progress = int(operation.get("progress"))
        if not 0 <= record_id <= 0xFFFF:
            raise ValueError("record_id must be between 0 and 65535")
        if not 0 <= progress <= 0xFFFFFFFF:
            raise ValueError("progress must be between 0 and 4294967295")
        if record_id == 0 and progress != 0:
            raise ValueError("an empty active slot (record_id 0) must also have progress 0")

        before_row = decoded_before["active"][slot]
        data[slot * 2 : slot * 2 + 2] = record_id.to_bytes(2, "little")
        progress_offset = EMINENCE_PROGRESS_OFFSET + slot * 4
        data[progress_offset : progress_offset + 4] = progress.to_bytes(4, "little")
        after_blob = bytes(data)
        decoded_after = decode_eminence(after_blob, family)
        return after_blob, dict(before_row), dict(decoded_after["active"][slot])

    if kind == "completion":
        record_id = int(operation.get("record_id", -1))
        if not 0 <= record_id < 4096:
            raise ValueError("record_id must be between 0 and 4095")
        if "completed" not in operation:
            raise ValueError("completion edits require completed")
        offset = EMINENCE_COMPLETE_OFFSET + record_id // 8
        mask = 1 << (record_id % 8)
        before_completed = bool(blob[offset] & mask)
        if bool(operation["completed"]):
            data[offset] |= mask
        else:
            data[offset] &= ~mask
        after_blob = bytes(data)
        decode_eminence(after_blob, family)
        return (
            after_blob,
            {"record_id": record_id, "completed": before_completed},
            {"record_id": record_id, "completed": bool(after_blob[offset] & mask)},
        )

    raise ValueError("kind must be either 'active_slot' or 'completion'")


def build_eminence_edit_plan(
    connection,
    *,
    char_id: int,
    operation: dict[str, Any] | None = None,
    adapter_family: str = "unknown",
) -> PackedEditPlan:
    char_id = int(char_id)
    operation = dict(operation or {})
    family = str(adapter_family or "unknown").strip().lower()
    capability = "eminence"
    column = "eminence"
    issues: list[PackedIssue] = []
    schema = discover_character_schema(connection)

    if family not in _VERIFIED_FAMILIES:
        issues.append(PackedIssue("adapter_unverified", "Eminence packed writes are verified only for Topaz and LSB."))
    if (schema.packed_fields or {}).get(capability) != "chars.eminence":
        issues.append(PackedIssue("packed_location_unverified", "Expected Eminence state at chars.eminence."))

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(PackedIssue("character_online", "Character is online; Eminence writes are blocked."))
    elif state.online is None:
        issues.append(PackedIssue("online_state_unknown", "Character online state could not be verified."))

    before_blob = _chars_blob(connection, schema, char_id, column)
    if before_blob is None:
        issues.append(PackedIssue("blob_missing", "Character has no chars.eminence BLOB."))

    after_blob: bytes | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    if before_blob is not None and family in _VERIFIED_FAMILIES:
        try:
            after_blob, before, after = _edit_blob(before_blob, family, operation)
        except (EminenceCodecError, TypeError, ValueError) as exc:
            issues.append(PackedIssue("invalid_packed_edit", str(exc)))

    if before_blob is not None and after_blob == before_blob and not any(issue.blocking for issue in issues):
        issues.append(PackedIssue("no_change", "Requested Eminence edit does not change the stored value."))

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
