"""Explicit in-memory registry for independent, read-only telemetry replay clients."""
from __future__ import annotations

from dataclasses import dataclass, field

from .replay import RecordedTelemetryReplay
from .file_bridge import FileTelemetryBridge
from .telemetry import TelemetryFrame


@dataclass
class ReplayRegistry:
    """No filesystem discovery, process attachment, or implicit active client."""

    _clients: dict[str, RecordedTelemetryReplay] = field(default_factory=dict)
    _feeds: dict[str, FileTelemetryBridge] = field(default_factory=dict)

    def add(self, client_id: str, replay: RecordedTelemetryReplay) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("invalid client id")
        if replay.feed.client_id != client_id:
            raise ValueError("replay belongs to a different client")
        if client_id in self._clients or client_id in self._feeds:
            raise ValueError("client already registered")
        self._clients[client_id] = replay

    def add_feed(self, client_id: str, bridge: FileTelemetryBridge) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError('invalid client id')
        if bridge.feed.client_id != client_id or client_id in self.client_ids():
            raise ValueError('feed client mismatch or already registered')
        self._feeds[client_id] = bridge

    def poll_feed(self, client_id: str, *, max_frames: int = 100) -> int:
        return self._feeds[client_id].poll(max_frames=max_frames)

    def remove(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        self._feeds.pop(client_id, None)

    def client_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self._clients) | set(self._feeds)))

    def frame(self, client_id: str) -> TelemetryFrame | None:
        replay = self._clients.get(client_id)
        return (replay.feed._latest if replay is not None else
                self._feeds[client_id].feed._latest if client_id in self._feeds else None)

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
        } for client_id, replay in sorted(self._clients.items())) + tuple({
            'client_id': client_id,
            'observed': bridge.feed._latest is not None,
            'zone_id': (bridge.feed._latest.snapshot.position.zone_id
                        if bridge.feed._latest is not None else None),
            'remaining_frames': 0,
            'read_only': True,
            'source': 'file_feed',
        } for client_id, bridge in sorted(self._feeds.items()))
