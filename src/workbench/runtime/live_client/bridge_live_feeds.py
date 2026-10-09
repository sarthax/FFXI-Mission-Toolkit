"""Read-only live feed handoff for authenticated localhost bridge sessions.

The caller runs the listener explicitly. No game writes, automatic background
service, or Capture database mutation is performed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json

from .bridge_listener import BridgeListener
from .bridge_protocol import BridgeLane, BridgeKind
from .bridge_telemetry import decode_bridge_telemetry
from .feed import TelemetryFeedAdapter
from .telemetry import TelemetryFrame


@dataclass
class BridgeLiveFeeds:
    listener: BridgeListener
    _feeds: dict[str, tuple[str, str, TelemetryFeedAdapter]] = field(default_factory=dict, init=False)

    def accept_and_update(self, *, now: float | None = None) -> tuple[TelemetryFrame, ...]:
        """Validate entire incoming batch before publishing to read-only feeds.

        Capture messages remain in the listener's capture mailbox for canonical
        ingestion by a separate, authorized Capture adapter.
        """
        messages = self.listener.accept_batch(now=now)
        if not messages:
            return ()
        first = messages[0]
        incoming = [message for message in messages if message.lane is BridgeLane.TELEMETRY]
        if not incoming:
            return ()
        frames = [decode_bridge_telemetry(message) for message in incoming]
        previous = self._feeds.get(first.client_id)
        if previous and previous[:2] == (first.session_id, first.generation):
            latest = previous[2]._latest
            if latest and frames[0].snapshot.observed_at <= latest.snapshot.observed_at:
                raise ValueError("stale bridge telemetry against active session")
        for older, newer in zip(frames, frames[1:]):
            if newer.snapshot.observed_at <= older.snapshot.observed_at:
                raise ValueError("nonmonotonic bridge telemetry batch")
        feed = previous[2] if previous and previous[:2] == (first.session_id, first.generation) else TelemetryFeedAdapter(first.client_id)
        # Frames were decoded once, with their provenance; no JSON re-interpretation.
        feed._latest = frames[-1]
        self._feeds[first.client_id] = (first.session_id, first.generation, feed)
        return tuple(frames)

    def feed(self, client_id: str) -> TelemetryFeedAdapter | None:
        entry = self._feeds.get(client_id)
        return entry[2] if entry else None

    def forget(self, client_id: str) -> None:
        self._feeds.pop(client_id, None)
