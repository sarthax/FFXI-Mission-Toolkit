"""Strict read-only telemetry ingestion for a future native or addon bridge.

Wire data is untrusted. This module does not attach to a process or issue commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .entities import EntityKind, EntityObservation
from .models import ClientSnapshot, Position


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("expected finite number")
    return float(value)


def _integer(value: Any, *, low: int = 0, high: int = 0xFFFFFFFF) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid integer")
    return value


def _string(value: Any, *, limit: int = 200, nonempty: bool = True) -> str:
    if not isinstance(value, str) or len(value) > limit or (nonempty and not value.strip()):
        raise ValueError("invalid text")
    return value


def _position(data: dict) -> Position:
    if not isinstance(data, dict):
        raise ValueError("invalid position")
    return Position(zone_id=_integer(data["zone_id"], high=65535),
                    x=_number(data["x"]), y=_number(data["y"]), z=_number(data["z"]),
                    heading=_number(data.get("heading", 0)))


@dataclass(frozen=True)
class TelemetryFrame:
    snapshot: ClientSnapshot
    entities: tuple[EntityObservation, ...]
    observation_scope: str = "unspecified"
    entities_truncated: bool = False
    activity: dict | None = None


def _activity(data: Any, observed_at: float) -> dict | None:
    """Optional combat/dialog block. Untrusted: every field is type- and size-bounded; bad input is dropped,
    never raised, so a malformed activity block cannot take down position telemetry."""
    if not isinstance(data, dict):
        return None

    def num(row: Any, key: str, default: int = 0) -> int:
        v = row.get(key, default) if isinstance(row, dict) else default
        return v if type(v) is int and -2**40 < v < 2**40 else default

    def rows(key: str, limit: int, build) -> list:
        raw = data.get(key)
        if not isinstance(raw, list):
            return []
        out = []
        for row in raw[:limit]:
            if isinstance(row, dict):
                out.append(build(row))
        return out

    def stamp(row: dict) -> float:
        return round(observed_at - num(row, "age_ms") / 1000.0, 3)

    def text(row: dict, key: str, limit: int) -> str:
        v = row.get(key)
        return v[:limit] if isinstance(v, str) else ""

    ev = data.get("event") if isinstance(data.get("event"), dict) else {}
    return {
        "hp": num(data, "hp"), "max_hp": num(data, "max_hp"), "mp": num(data, "mp"), "max_mp": num(data, "max_mp"),
        "tp": num(data, "tp"), "hpp": num(data, "hpp"), "mpp": num(data, "mpp"),
        "server_status": num(data, "server_status"), "target_id": num(data, "target_id"),
        "attackers": rows("attackers", 16, lambda r: {"actor": num(r, "actor"), "target": num(r, "target"), "at": stamp(r)}),
        "combat": rows("combat", 32, lambda r: {"seq": num(r, "seq"), "target": num(r, "target"), "amount": num(r, "amount"),
                                                 "kind": num(r, "kind"), "at": stamp(r)}),
        "speech": rows("speech", 16, lambda r: {"seq": num(r, "seq"), "actor": num(r, "actor"), "client_index": num(r, "client_index"),
                                                 "message_id": num(r, "message_id"), "name_hidden": bool(r.get("name_hidden")), "at": stamp(r)}),
        "chat": rows("chat", 16, lambda r: {"kind": num(r, "kind"), "sender": text(r, "sender", 32), "message": text(r, "message", 150), "at": stamp(r)}),
        "event": {"active": bool(ev.get("active")), "npc_id": num(ev, "npc_id"), "client_index": num(ev, "client_index"),
                  "event_id": num(ev, "event_id"), "form34": bool(ev.get("form34"))},
    }


def decode_frame(payload: dict, *, max_entities: int = 4096) -> TelemetryFrame:
    """Decode a versioned snapshot. Client entity slots do not imply server IDs."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported telemetry schema")
    client_id = _string(payload["client_id"])
    observed_at = _number(payload["observed_at"])
    instance_hint = payload.get("instance_hint")
    if instance_hint is not None:
        instance_hint = _string(instance_hint)
    snapshot = ClientSnapshot(
        client_id=client_id,
        version=_string(payload["client_version"]),
        character=_string(payload["character"]),
        position=_position(payload["position"]),
        observed_at=observed_at,
        adapter=_string(payload["adapter"]),
        instance_hint=instance_hint,
    )
    raw_entities = payload.get("entities", [])
    if not isinstance(raw_entities, list) or len(raw_entities) > max_entities:
        raise ValueError("invalid entity observations")
    entities = []
    for row in raw_entities:
        if not isinstance(row, dict):
            raise ValueError("invalid entity")
        if row.get("server_entity_id") is None:
            server_id = None
        else:
            server_id = _integer(row["server_entity_id"])
        hint = row.get("instance_hint", instance_hint)
        if hint is not None:
            hint = _string(hint)
        roles = row.get("target_roles", [])
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise ValueError("invalid target roles")
        entities.append(EntityObservation(
            client_id=client_id,
            client_index=_integer(row["client_index"], high=65535),
            kind=EntityKind(row.get("kind", "unknown")),
            name=_string(row["name"], nonempty=False),
            position=_position(row["position"]),
            observed_at=observed_at,
            server_entity_id=server_id,
            instance_hint=hint,
            raw_entity_type=row.get("raw_entity_type"),
            raw_spawn_flags=row.get("raw_spawn_flags"),
            raw_status=row.get("raw_status"),
            target_roles=tuple(roles),
        ))
    scope = payload.get("observation_scope", "unspecified")
    truncated = payload.get("entities_truncated", False)
    if scope not in ("unspecified", "selected_targets", "bounded_loaded_entities") or type(truncated) is not bool:
        raise ValueError("invalid entity observation scope")
    if scope == "bounded_loaded_entities" and len(entities) > 256:
        raise ValueError("bounded inventory exceeds 32 entities")
    return TelemetryFrame(snapshot, tuple(entities), scope, truncated, _activity(payload.get("activity"), observed_at))
