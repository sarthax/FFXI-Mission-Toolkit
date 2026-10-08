"""Deterministic read-only telemetry replay and explicit connection status.

No process attachment, timers, or implicit operating-system client discovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from .feed import TelemetryFeedAdapter


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    STALE = "stale"


@dataclass(frozen=True)
class FeedHealth:
    state: ConnectionState
    client_id: str
    last_observed_at: float | None
    frame_count: int


class RecordedTelemetryReplay:
    """Explicitly advance validated fixture frames without a live FFXI client."""

    def __init__(self, client_id: str, frames: Sequence[dict]):
        self.feed = TelemetryFeedAdapter(client_id)
        self._frames = tuple(frames)
        self._index = 0
        self._count = 0

    @property
    def remaining(self) -> int:
        return len(self._frames) - self._index

    def advance(self):
        if not self.remaining:
            raise StopIteration("no more recorded telemetry")
        # Failed validation must not consume a frame or damage last-good state.
        frame = self.feed.ingest(self._frames[self._index])
        self._index += 1
        self._count += 1
        return frame

    def health(self, *, now: float, max_age: float = 5.0) -> FeedHealth:
        """Use caller-supplied time; replay timestamps need not be wall time."""
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not isfinite(now):
            raise ValueError("invalid reference time")
        if isinstance(max_age, bool) or not isinstance(max_age, (int, float)) or not isfinite(max_age) or max_age < 0:
            raise ValueError("invalid maximum age")
        if self._count == 0:
            return FeedHealth(ConnectionState.DISCONNECTED, self.feed.client_id, None, 0)
        observed_at = self.feed.snapshot().observed_at
        age = now - observed_at
        state = ConnectionState.STALE if age < 0 or age > max_age else ConnectionState.CONNECTED
        return FeedHealth(state, self.feed.client_id, observed_at, self._count)
