"""Explicit in-memory registry for independent, read-only telemetry replay clients."""
from __future__ import annotations

from dataclasses import dataclass, field

from .replay import RecordedTelemetryReplay
from .telemetry import TelemetryFrame


@dataclass
class ReplayRegistry:
    """No filesystem discovery, process attachment, or implicit active client."""

    _clients: dict[str, RecordedTelemetryReplay] = field(default_factory=dict)

    def add(self, client_id: str, replay: RecordedTelemetryReplay) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("invalid client id")
        if replay.feed.client_id != client_id:
            raise ValueError("replay belongs to a different client")
        if client_id in self._clients:
            raise ValueError("client already registered")
        self._clients[client_id] = replay

    def remove(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def client_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._clients))

    def frame(self, client_id: str) -> TelemetryFrame | None:
        replay = self._clients.get(client_id)
        return replay.feed._latest if replay is not None else None

    def advance(self, client_id: str) -> TelemetryFrame:
        if client_id not in self._clients:
            raise KeyError("client not registered")
        return self._clients[client_id].advance()

    def status(self) -> tuple[dict, ...]:
        return tuple({
            "client_id": client_id,
            "observed": replay.feed._latest is not None,
            "zone_id": (replay.feed._latest.snapshot.position.zone_id
                        if replay.feed._latest is not None else None),
            "remaining_frames": replay.remaining,
            "read_only": True,
        } for client_id, replay in sorted(self._clients.items()))
