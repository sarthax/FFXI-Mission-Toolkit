"""Transport-neutral data contracts for live-client spatial development."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Optional


@dataclass(frozen=True)
class Position:
    zone_id: int
    x: float
    y: float
    z: float
    heading: float = 0.0

    def __post_init__(self) -> None:
        if not (0 <= self.zone_id <= 65535):
            raise ValueError("invalid zone ID")
        if not all(isfinite(v) for v in (self.x, self.y, self.z, self.heading)):
            raise ValueError("coordinates must be finite")


@dataclass(frozen=True)
class ClientSnapshot:
    client_id: str
    version: str
    character: str
    position: Position
    observed_at: float
    adapter: str
    instance_hint: Optional[str] = None


@dataclass(frozen=True)
class Waypoint:
    name: str
    position: Position
    source: str = "manual"


@dataclass(frozen=True)
class PathSample:
    observed_at: float
    position: Position
    client_id: str


class DevelopmentAction(str, Enum):
    NUDGE = "nudge"
    WARP_WAYPOINT = "warp_waypoint"
    WARP_ENTITY = "warp_entity"
    SET_SPEED = "set_speed"
    SET_VISIBILITY = "set_visibility"
    PLACE_ENTITY_CANDIDATE = "place_entity_candidate"
    VALIDATE_NAVMESH = "validate_navmesh"


WRITE_ACTIONS = frozenset({
    DevelopmentAction.NUDGE,
    DevelopmentAction.WARP_WAYPOINT,
    DevelopmentAction.WARP_ENTITY,
    DevelopmentAction.SET_SPEED,
    DevelopmentAction.SET_VISIBILITY,
})


def validate_action(action: DevelopmentAction, *, authorized_dev_session: bool,
                    adapter_supports_writes: bool, version_verified: bool) -> None:
    """Fail closed for operations that modify the live game client."""
    if action in WRITE_ACTIONS and not (
        authorized_dev_session and adapter_supports_writes and version_verified
    ):
        raise PermissionError("live client writes require an authorized, version-verified development session")
