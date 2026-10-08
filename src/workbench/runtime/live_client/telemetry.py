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
        entities.append(EntityObservation(
            client_id=client_id,
            client_index=_integer(row["client_index"], high=65535),
            kind=EntityKind(row.get("kind", "unknown")),
            name=_string(row["name"], nonempty=False),
            position=_position(row["position"]),
            observed_at=observed_at,
            server_entity_id=server_id,
            instance_hint=hint,
        ))
    return TelemetryFrame(snapshot, tuple(entities))
