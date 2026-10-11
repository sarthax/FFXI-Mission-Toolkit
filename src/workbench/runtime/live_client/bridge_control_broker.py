"""Bounded, session-bound command delivery state for the local Live Client bridge.

No game writes. The only dispatchable command is a read-only capability probe.
Reserved movement/stop names are NOT executable until separately authorized.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
import time

from .bridge_peers import PeerIdentity
from .bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane, match_response

PROBE = b'capabilities_probe'


@dataclass
class PendingProbe:
    command: BridgeEnvelope
    deadline: float
    state: str = "queued"
    response: BridgeEnvelope | None = None


@dataclass
class ControlBroker:
    ttl: float = 3.0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _pending: dict[str, PendingProbe] = field(default_factory=dict, repr=False)
    _sequence: int = 0

    def _expire(self, now: float) -> None:
        for client, pending in list(self._pending.items()):
            if now >= pending.deadline and pending.state in ("queued", "delivered"):
                pending.state = "expired"

    def schedule_probe(self, identity: PeerIdentity, *, now: float | None = None) -> BridgeEnvelope:
        clock = time.monotonic() if now is None else now
        if not 0 <= clock < float("inf") or not 0 < self.ttl <= 10:
            raise ValueError("invalid control clock or TTL")
        with self._lock:
            self._expire(clock)
            previous = self._pending.get(identity.client_id)
            if previous and previous.state in ("queued", "delivered"):
                raise ValueError("control probe already pending")
            self._sequence += 2
            command = BridgeEnvelope(1, BridgeLane.CONTROL, BridgeKind.COMMAND,
                identity.client_id, identity.session_id, identity.generation,
                self._sequence, secrets.token_hex(12), PROBE)
            self._pending[identity.client_id] = PendingProbe(command, clock + self.ttl)
            return command

    def next_for(self, identity: PeerIdentity, *, now: float | None = None) -> BridgeEnvelope | None:
        clock = time.monotonic() if now is None else now
        with self._lock:
            self._expire(clock)
            pending = self._pending.get(identity.client_id)
            if pending is None or pending.state != "queued":
                return None
            command = pending.command
            if (command.session_id, command.generation) != (identity.session_id, identity.generation):
                pending.state = "cancelled"
                return None
            pending.state = "delivered"
            return command

    def resolve(self, identity: PeerIdentity, response: BridgeEnvelope, *, now: float | None = None) -> bool:
        clock = time.monotonic() if now is None else now
        with self._lock:
            self._expire(clock)
            pending = self._pending.get(identity.client_id)
            if pending is None or pending.state != "delivered":
                return False
            if response.kind not in (BridgeKind.ACK, BridgeKind.REJECT) or not match_response(pending.command, response):
                return False
            if (identity.session_id, identity.generation) != (pending.command.session_id, pending.command.generation):
                return False
            pending.response = response
            pending.state = "acknowledged" if response.kind is BridgeKind.ACK else "rejected"
            return True

    def status(self, client_id: str, *, now: float | None = None) -> dict[str, object]:
        clock = time.monotonic() if now is None else now
        with self._lock:
            self._expire(clock)
            pending = self._pending.get(client_id)
            if not pending:
                return {"state": "none", "request_id": None}
            return {"state": pending.state, "request_id": pending.command.request_id,
                    "response": pending.response.payload.decode("utf-8", "replace")[:128] if pending.response else None}

    def cancel(self, client_id: str | None = None) -> None:
        with self._lock:
            targets = [client_id] if client_id else list(self._pending)
            for key in targets:
                pending = self._pending.get(key)
                if pending and pending.state in ("queued", "delivered"):
                    pending.state = "cancelled"
