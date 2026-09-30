"""Conservative interaction-candidate reconstruction for capture_events rows.

capture_events has a real per-zone sequence but no shared timestamp/transaction id. This module
therefore groups only contiguous, identity-compatible rows and explicitly labels the result a
candidate rather than asserting a gameplay transaction.
"""
from __future__ import annotations


def reconstruct_interaction_candidates(rows, *, max_seq_gap: int = 2) -> list[dict]:
    """Group ordered capture_events rows without inventing cross-row semantics.

    A group is split when zone changes, the observed sequence jumps beyond max_seq_gap, a new
    explicit entity conflicts with the current entity, or a different explicit CSID begins.
    Missing entity/CSID fields may remain inside an otherwise compatible contiguous group.
    """
    candidates: list[dict] = []
    current: dict | None = None

    def finish():
        nonlocal current
        if current is None:
            return
        current["row_count"] = len(current["rows"])
        current["complete_signal"] = bool(
            current.get("csid") and (
                current.get("options") or current.get("messages") or len(current["rows"]) > 1
            )
        )
        current["basis"] = "contiguous capture_events rows with compatible zone/entity/CSID"
        candidates.append(current)
        current = None

    for source in rows:
        row = dict(source)
        zone = row.get("zone_db")
        seq = row.get("seq")
        entity_id = row.get("entity_id")
        event_hex = row.get("event_hex")

        split = False
        if current is not None:
            prev_seq = current["end_seq"]
            split = (
                zone != current["zone_db"]
                or seq is None
                or prev_seq is None
                or seq - prev_seq > max_seq_gap
                or (entity_id is not None and current.get("entity_id") is not None
                    and entity_id != current["entity_id"])
                or (event_hex and current.get("csid") and event_hex != current["csid"])
            )
        if split:
            finish()

        if current is None:
            current = {
                "candidate_id": f"{zone}:{seq}",
                "zone_db": zone,
                "start_seq": seq,
                "end_seq": seq,
                "entity_id": entity_id,
                "entity_name": row.get("entity_name"),
                "csid": event_hex,
                "options": [],
                "messages": [],
                "directions": [],
                "rows": [],
            }

        current["end_seq"] = seq
        if current.get("entity_id") is None and entity_id is not None:
            current["entity_id"] = entity_id
            current["entity_name"] = row.get("entity_name")
        if current.get("csid") is None and event_hex:
            current["csid"] = event_hex
        if row.get("option") is not None and row["option"] not in current["options"]:
            current["options"].append(row["option"])
        if row.get("message_id") is not None:
            message = {
                "message_id": row["message_id"],
                "dialog_text": row.get("dialog_text"),
                "seq": seq,
            }
            if message not in current["messages"]:
                current["messages"].append(message)
        direction = row.get("direction")
        if direction and direction not in current["directions"]:
            current["directions"].append(direction)
        current["rows"].append(row)

    finish()
    return candidates
