"""Pure spatial operations shared by a future live adapter and Zone Editor.

No database updates or client-memory writes happen in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import dist, isfinite
from typing import Iterable

from .models import PathSample, Position, Waypoint


@dataclass(frozen=True)
class PlacementCandidate:
    """Preview-only spawn proposal; must use Zone Editor's existing write flow."""
    entity_kind: str
    position: Position
    source_client: str
    source_observed_at: float

    def __post_init__(self):
        if self.entity_kind not in ("npc", "mob"):
            raise ValueError("entity kind must be npc or mob")
        if not isfinite(self.source_observed_at):
            raise ValueError("invalid observation time")


def placement_from_sample(kind: str, sample: PathSample) -> PlacementCandidate:
    return PlacementCandidate(kind, sample.position, sample.client_id, sample.observed_at)


def nearby_waypoints(position: Position, waypoints: Iterable[Waypoint],
                     max_distance: float | None = None) -> list[tuple[Waypoint, float]]:
    if max_distance is not None and (not isfinite(max_distance) or max_distance < 0):
        raise ValueError("invalid distance")
    found = []
    for waypoint in waypoints:
        if waypoint.position.zone_id != position.zone_id:
            continue
        distance = dist((position.x, position.y, position.z),
                        (waypoint.position.x, waypoint.position.y, waypoint.position.z))
        if max_distance is None or distance <= max_distance:
            found.append((waypoint, distance))
    return sorted(found, key=lambda item: (item[1], item[0].name))


def split_path_by_zone(samples: Iterable[PathSample]) -> list[list[PathSample]]:
    """Preserve zone/source/session/instance/visit and time discontinuities."""
    segments: list[list[PathSample]] = []
    def context(point):
        return (point.position.zone_id, point.client_id, point.instance_hint,
                point.adapter, point.client_version, point.session_id,
                point.session_generation, point.recorded_segment)
    for sample in samples:
        previous = segments[-1][-1] if segments else None
        if previous is None or context(previous) != context(sample) or sample.observed_at <= previous.observed_at:
            segments.append([])
        segments[-1].append(sample)
    return segments
