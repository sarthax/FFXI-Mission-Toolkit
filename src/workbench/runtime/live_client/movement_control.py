"""Fail-closed *simulation-only* movement control contract.

This is deliberately transport-neutral.  No memory, packet, socket or process
write path is exposed; an authorized runtime adapter must be implemented and
separately validated before a real movement capability can be advertised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from time import monotonic

from .bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane
from .bridge_mailbox import BridgeMailbox, SimulatedBridgeClient


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if any(type(n) not in (int, float) or not isfinite(n) for n in (self.x, self.y, self.z)):
            raise ValueError("nonfinite or invalid XYZ")


@dataclass(frozen=True)
class ControlIdentity:
    client_id: str
    session_id: str
    generation: str
    zone_id: int
    build_verified: bool = False

    def __post_init__(self) -> None:
        if type(self.zone_id) is not int or not 1 <= self.zone_id <= 65535:
            raise ValueError("invalid zone ID")


@dataclass
class MovementControlGate:
    """One selected client/zone; simulated requests always receive REJECT.

    Expiration uses monotonic seconds supplied by the caller, so stale requests
    cannot become valid on wall-clock rollback. STOP always disarms, even if
    telemetry has gone stale, and never waits for queued capture observations.
    """
    mailbox: BridgeMailbox
    zone_id: int
    max_nudge: float = 3.0
    ttl_seconds: float = 2.0
    armed: bool = False
    last_observation_at: float | None = None
    last_position: Position | None = None
    next_sequence: int = 0
    audit: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if type(self.zone_id) is not int or not 1 <= self.zone_id <= 65535:
            raise ValueError("invalid zone")
        if not 0 < self.max_nudge <= 10 or not 0 < self.ttl_seconds <= 10:
            raise ValueError("unsafe movement bounds")

    def observe(self, identity: ControlIdentity, position: Position, *, now: float | None = None) -> None:
        now = monotonic() if now is None else now
        if not isfinite(now):
            raise ValueError("invalid observation clock")
        if (identity.client_id, identity.session_id, identity.generation) != (
            self.mailbox.client_id, self.mailbox.session_id, self.mailbox.generation
        ) or identity.zone_id != self.zone_id:
            self.disarm("identity_or_zone_changed")
            raise ValueError("observation identity or zone mismatch")
        if self.last_observation_at is not None and now <= self.last_observation_at:
            self.disarm("nonmonotonic_observation")
            raise ValueError("stale observation")
        self.last_position = position
        self.last_observation_at = now

    def arm_simulation(self, *, explicit_consent: bool) -> None:
        if not explicit_consent or self.last_position is None:
            raise ValueError("explicit consent and observation required")
        self.armed = True

    def disarm(self, reason: str = "stop") -> None:
        self.armed = False
        self.audit.append({"event": "disarmed", "reason": reason})

    def stop(self) -> None:
        """Locally disarm immediately; adapter STOP integration is future work."""
        self.disarm("operator_stop")

    def simulate_nudge(self, identity: ControlIdentity, target: Position,
                       request_id: str, *, now: float | None = None) -> BridgeEnvelope:
        now = monotonic() if now is None else now
        if not isfinite(now):
            raise ValueError("invalid request clock")
        if not self.armed:
            raise PermissionError("movement simulation is disarmed")
        if (identity.client_id, identity.session_id, identity.generation) != (
            self.mailbox.client_id, self.mailbox.session_id, self.mailbox.generation
        ) or identity.zone_id != self.zone_id:
            self.disarm("identity_or_zone_changed")
            raise PermissionError("client/session/zone mismatch")
        if self.last_observation_at is None or now < self.last_observation_at or now - self.last_observation_at > self.ttl_seconds:
            self.disarm("stale_observation")
            raise PermissionError("fresh telemetry required")
        assert self.last_position is not None
        distance = sum((a - b) ** 2 for a, b in zip(
            (target.x, target.y, target.z),
            (self.last_position.x, self.last_position.y, self.last_position.z))) ** 0.5
        if not isfinite(distance) or distance > self.max_nudge:
            raise ValueError("nudge outside allowed distance")
        if not request_id or len(request_id) > 128:
            raise ValueError("invalid request id")
        seq = max(self.next_sequence, self.mailbox._sequences.get(BridgeLane.CONTROL, -1) + 1)
        request = BridgeEnvelope(
            1, BridgeLane.CONTROL, BridgeKind.COMMAND,
            identity.client_id, identity.session_id, identity.generation,
            seq, request_id, b'{"action":"simulate_nudge","writes_enabled":false}',
        )
        self.mailbox.submit(request)
        self.next_sequence = seq + 1
        response = SimulatedBridgeClient(self.mailbox).respond(request, seq + 1)
        self.audit.append({"event": "simulated_nudge_rejected", "request_id": request_id,
                           "zone_id": self.zone_id, "reason": "writes_not_supported",
                           "requested_distance": distance})
        return response
