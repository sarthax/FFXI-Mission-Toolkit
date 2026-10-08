"""Read-only client entity observations and overlay matching.

Client slots/indexes are *not* interchangeable with server entity IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable

from .models import Position


class EntityKind(str, Enum):
    PLAYER = "player"
    NPC = "npc"
    MOB = "mob"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EntityObservation:
    client_id: str
    client_index: int
    kind: EntityKind
    name: str
    position: Position
    observed_at: float
    server_entity_id: int | None = None
    instance_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.client_id or not 0 <= self.client_index <= 65535:
            raise ValueError("invalid client identity")
        if self.server_entity_id is not None and not 0 <= self.server_entity_id <= 0xFFFFFFFF:
            raise ValueError("invalid server entity ID")
        if not isfinite(self.observed_at):
            raise ValueError("invalid observation time")


def overlay_observations(observations: Iterable[EntityObservation], *,
                         zone_id: int, client_id: str,
                         instance_hint: str | None = None) -> tuple[EntityObservation, ...]:
    """Select only observations belonging to the viewing client's zone.

    If a specific instance is selected, unknown-instance observations are excluded,
    rather than guessing which instance they belong to.
    """
    return tuple(o for o in observations
                 if o.client_id == client_id and o.position.zone_id == zone_id
                 and (instance_hint is None or o.instance_hint == instance_hint))


def match_server_id(observations: Iterable[EntityObservation], server_entity_id: int
                    ) -> tuple[EntityObservation, ...]:
    """Matches require an explicitly observed server identity, never client index."""
    return tuple(o for o in observations if o.server_entity_id == server_entity_id)
