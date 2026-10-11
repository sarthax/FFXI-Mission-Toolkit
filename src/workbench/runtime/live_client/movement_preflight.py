"""Pure, fail-closed preflight for future authorized test-client movement.

This module is not a movement executor and grants no write capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from .models import ClientSnapshot, DevelopmentAction, Position, validate_action


@dataclass(frozen=True)
class MovementPreflight:
    allowed: bool
    reasons: tuple[str, ...]
    distance: float | None
    action: str = "nudge"
    executed: bool = False


def evaluate_nudge(*, snapshot: ClientSnapshot | None, target: Position,
                   selected_client: str, selected_character: str,
                   expected_zone: int, now: float, max_age_seconds: float = 2.0,
                   max_step: float = 1.0, authorized_dev_session: bool = False,
                   adapter_supports_writes: bool = False,
                   version_verified: bool = False,
                   independent_alignment_verified: bool = False,
                   receiver_connected: bool = False) -> MovementPreflight:
    """Assess a bounded same-zone proposal without issuing any write.

    Callers must revalidate immediately before a separate future executor.
    """
    reasons: list[str] = []
    distance = None
    if not isinstance(selected_client, str) or not selected_client or not isinstance(selected_character, str) or not selected_character:
        reasons.append("invalid_selection")
    if type(expected_zone) is not int or not 1 <= expected_zone <= 65535:
        reasons.append("invalid_zone")
    if type(now) not in (int, float) or not isfinite(now):
        reasons.append("invalid_clock")
    if type(max_age_seconds) not in (int, float) or not isfinite(max_age_seconds) or not 0 < max_age_seconds <= 5:
        reasons.append("invalid_age_limit")
    if type(max_step) not in (int, float) or not isfinite(max_step) or not 0 < max_step <= 1:
        reasons.append("invalid_step_limit")
    if not receiver_connected:
        reasons.append("receiver_not_connected")
    if not isinstance(snapshot, ClientSnapshot):
        reasons.append("no_live_snapshot")
    else:
        if snapshot.client_id != selected_client or snapshot.character != selected_character:
            reasons.append("identity_mismatch")
        if snapshot.position.zone_id != expected_zone or target.zone_id != expected_zone:
            reasons.append("zone_mismatch")
        age = now - snapshot.observed_at
        if not isfinite(age) or age < 0 or age > max_age_seconds:
            reasons.append("stale_snapshot")
        distance = sqrt(sum((getattr(target, axis)-getattr(snapshot.position, axis))**2 for axis in ("x","y","z")))
        if not isfinite(distance) or distance < 1e-6 or distance > max_step:
            reasons.append("step_out_of_bounds")
    if not independent_alignment_verified:
        reasons.append("alignment_unverified")
    try:
        validate_action(DevelopmentAction.NUDGE,
                        authorized_dev_session=authorized_dev_session,
                        adapter_supports_writes=adapter_supports_writes,
                        version_verified=version_verified)
    except PermissionError:
        reasons.append("write_authorization_unavailable")
    return MovementPreflight(not reasons, tuple(reasons), distance)
