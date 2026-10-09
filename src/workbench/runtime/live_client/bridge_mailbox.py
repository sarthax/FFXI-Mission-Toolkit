"""Bounded local bridge broker for simulated clients and future localhost adapters.

No network listener, OS process attachment, or game write capability is enabled.
A future local transport may use this broker to enforce independent lane budgets.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane, match_response


@dataclass
class BridgeMailbox:
    client_id: str
    session_id: str
    generation: str
    control_limit: int = 32
    telemetry_limit: int = 128
    capture_limit: int = 256
    _queues: dict[BridgeLane, deque[BridgeEnvelope]] = field(
        default_factory=lambda: {lane: deque() for lane in BridgeLane}, init=False)
    _sequences: dict[BridgeLane, int] = field(default_factory=dict, init=False)
    capture_dropped: int = field(default=0, init=False)

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (self.client_id, self.session_id, self.generation)):
            raise ValueError("invalid mailbox source")
        if any(type(limit) is not int or limit < 1 or limit > 4096 for limit in
               (self.control_limit, self.telemetry_limit, self.capture_limit)):
            raise ValueError("invalid mailbox limit")

    def submit(self, message: BridgeEnvelope) -> bool:
        if (message.client_id, message.session_id, message.generation) != (
                self.client_id, self.session_id, self.generation):
            raise ValueError("bridge client/session generation mismatch")
        last = self._sequences.get(message.lane, -1)
        if message.sequence <= last:
            raise ValueError("nonmonotonic bridge lane sequence")
        queue = self._queues[message.lane]
        limit = {BridgeLane.CONTROL: self.control_limit,
                 BridgeLane.TELEMETRY: self.telemetry_limit,
                 BridgeLane.CAPTURE: self.capture_limit}[message.lane]
        if len(queue) >= limit:
            if message.lane is BridgeLane.CAPTURE:
                self.capture_dropped += 1
                self._sequences[message.lane] = message.sequence
                return False
            raise BufferError("bridge control/telemetry queue full")
        queue.append(message)
        self._sequences[message.lane] = message.sequence
        return True

    def receive(self) -> BridgeEnvelope | None:
        for lane in (BridgeLane.CONTROL, BridgeLane.TELEMETRY, BridgeLane.CAPTURE):
            if self._queues[lane]:
                return self._queues[lane].popleft()
        return None

    def pending(self, lane: BridgeLane) -> int:
        return len(self._queues[lane])


class SimulatedBridgeClient:
    """Simulates reject-only command acknowledgment, never writes to FFXI."""
    def __init__(self, mailbox: BridgeMailbox):
        self.mailbox = mailbox

    def respond(self, command: BridgeEnvelope, sequence: int) -> BridgeEnvelope:
        if command.kind is not BridgeKind.COMMAND or command.lane is not BridgeLane.CONTROL:
            raise ValueError("expected control command")
        response = BridgeEnvelope(
            schema_version=1, lane=BridgeLane.CONTROL, kind=BridgeKind.REJECT,
            client_id=self.mailbox.client_id, session_id=self.mailbox.session_id,
            generation=self.mailbox.generation, sequence=sequence,
            request_id=command.request_id, payload=b'{"reason":"writes_not_supported"}',
        )
        if not match_response(command, response):
            raise ValueError("invalid simulated command response")
        return response
