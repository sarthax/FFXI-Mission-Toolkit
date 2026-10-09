"""Transport-neutral envelopes for future localhost Live Client control and capture.

This module validates message *shape*, not authorization, game compatibility, or
packet fidelity. Real adapters must enforce capability, version and session gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import re


class BridgeLane(str, Enum):
    CONTROL = "control"
    TELEMETRY = "telemetry"
    CAPTURE = "capture"


class BridgeKind(str, Enum):
    COMMAND = "command"
    ACK = "ack"
    REJECT = "reject"
    OBSERVATION = "observation"
    CAPTURE_EVENT = "capture_event"
    HEARTBEAT = "heartbeat"


_ALLOWED = {
    BridgeLane.CONTROL: frozenset((BridgeKind.COMMAND, BridgeKind.ACK, BridgeKind.REJECT, BridgeKind.HEARTBEAT)),
    BridgeLane.TELEMETRY: frozenset((BridgeKind.OBSERVATION, BridgeKind.HEARTBEAT)),
    BridgeLane.CAPTURE: frozenset((BridgeKind.CAPTURE_EVENT,)),
}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_MAX_PAYLOAD = 64 * 1024


@dataclass(frozen=True)
class BridgeEnvelope:
    schema_version: int
    lane: BridgeLane
    kind: BridgeKind
    client_id: str
    session_id: str
    generation: str
    sequence: int
    request_id: str | None
    payload: bytes

    def __post_init__(self) -> None:
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise ValueError("unsupported bridge envelope schema")
        if not isinstance(self.lane, BridgeLane) or not isinstance(self.kind, BridgeKind):
            raise ValueError("invalid bridge lane/kind")
        if self.kind not in _ALLOWED[self.lane]:
            raise ValueError("bridge message kind not allowed on lane")
        for name in ("client_id", "session_id", "generation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError("invalid bridge identity: " + name)
        if type(self.sequence) is not int or not 0 <= self.sequence <= 2**63 - 1:
            raise ValueError("invalid bridge sequence")
        if self.request_id is not None and (not isinstance(self.request_id, str) or not _ID.fullmatch(self.request_id)):
            raise ValueError("invalid request ID")
        if self.kind in (BridgeKind.COMMAND, BridgeKind.ACK, BridgeKind.REJECT) and self.request_id is None:
            raise ValueError("control request/response requires request ID")
        if self.kind not in (BridgeKind.COMMAND, BridgeKind.ACK, BridgeKind.REJECT) and self.request_id is not None:
            raise ValueError("unsolicited event cannot claim a request ID")
        if type(self.payload) is not bytes or len(self.payload) > _MAX_PAYLOAD:
            raise ValueError("invalid bridge payload")


def match_response(request: BridgeEnvelope, response: BridgeEnvelope) -> bool:
    """Never correlate an acknowledgment from a different client or session."""
    return (
        request.lane is BridgeLane.CONTROL and request.kind is BridgeKind.COMMAND
        and response.lane is BridgeLane.CONTROL
        and response.kind in (BridgeKind.ACK, BridgeKind.REJECT)
        and (request.client_id, request.session_id, request.generation, request.request_id)
        == (response.client_id, response.session_id, response.generation, response.request_id)
        and response.sequence > request.sequence
    )


def lane_priority(lane: BridgeLane) -> int:
    """Smaller number is higher priority; transport must still enforce bounded queues."""
    return {BridgeLane.CONTROL: 0, BridgeLane.TELEMETRY: 1, BridgeLane.CAPTURE: 2}[lane]
