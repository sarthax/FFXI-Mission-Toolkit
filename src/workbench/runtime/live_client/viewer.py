"""Transport-neutral read-only projection for spatial viewer overlays."""
from __future__ import annotations

from dataclasses import asdict

from .entities import overlay_observations
from .telemetry import TelemetryFrame


def viewer_projection(frame: TelemetryFrame, *, zone_id: int,
                      client_id: str, instance_hint: str | None = None) -> dict:
    """Build JSON-compatible marker data, never infer server IDs from client slots.

    Explicit instance selection fails closed unless the player and entity hints match.
    """
    snapshot = frame.snapshot
    if snapshot.client_id != client_id or snapshot.position.zone_id != zone_id:
        return {"visible": False, "player": None, "entities": []}
    if instance_hint is not None and snapshot.instance_hint != instance_hint:
        return {"visible": False, "player": None, "entities": []}
    observations = overlay_observations(
        frame.entities, zone_id=zone_id, client_id=client_id,
        instance_hint=instance_hint,
    )
    return {
        "visible": True,
        "client_id": client_id,
        "zone_id": zone_id,
        "instance_hint": snapshot.instance_hint,
        "observed_at": snapshot.observed_at,
        "adapter": snapshot.adapter,
        "observation_scope": frame.observation_scope,
        "entities_truncated": frame.entities_truncated,
        "client_version": snapshot.version,
        "player": {"character": snapshot.character,
                   "position": asdict(snapshot.position)},
        "entities": [
            {"client_index": item.client_index, "kind": item.kind.value,
             "name": item.name, "position": asdict(item.position),
             "server_entity_id": item.server_entity_id,
             "instance_hint": item.instance_hint,
             "observed_at": item.observed_at}
            for item in observations
        ],
    }
