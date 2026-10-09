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
    instance_hint: Optional[str] = None
    adapter: Optional[str] = None
    client_version: Optional[str] = None
    session_id: Optional[str] = None
    session_generation: Optional[str] = None
    recorded_segment: Optional[int] = None
    observation_scope: str = "unspecified"
    entities_truncated: bool = False

    def __post_init__(self):
        if type(self.observed_at) not in (int, float) or not isfinite(self.observed_at):
            raise ValueError("invalid observation timestamp")
        if not isinstance(self.client_id, str) or not self.client_id.strip() or len(self.client_id) > 200:
            raise ValueError("invalid client id")
        for name in ("instance_hint", "adapter", "client_version", "session_id", "session_generation"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 200):
                raise ValueError("invalid path context " + name)
        if self.recorded_segment is not None and (type(self.recorded_segment) is not int or self.recorded_segment < 0):
            raise ValueError("invalid recorded segment")
        if self.observation_scope not in ("unspecified", "selected_targets", "bounded_loaded_entities") or type(self.entities_truncated) is not bool:
            raise ValueError("invalid entity observation scope")


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
