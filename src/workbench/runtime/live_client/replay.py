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

    @property
    def position(self) -> int:
        return self._index

    @property
    def total(self) -> int:
        return len(self._frames)

    def seek(self, position: int):
        """Seek to a one-based frame; reconstruct feed to permit backward movement."""
        if type(position) is not int or not 1 <= position <= len(self._frames):
            raise ValueError("frame position outside recording")
        candidate = TelemetryFeedAdapter(self.feed.client_id)
        last = None
        for payload in self._frames[:position]:
            last = candidate.ingest(payload)
        self.feed = candidate
        self._index = position
        self._count = position
        return last

    @property
    def next_frame_delay(self) -> float | None:
        """Recorded seconds until the next frame; no clock or background process."""
        if not self.remaining or self.feed._latest is None:
            return None
        from .telemetry import decode_frame
        next_frame = decode_frame(self._frames[self._index])
        return max(0.0, next_frame.snapshot.observed_at - self.feed._latest.snapshot.observed_at)

    def path_points(self, *, max_points: int = 1000) -> list[dict]:
        """Bounded, zone-preserving recording trace up to current frame."""
        from .telemetry import decode_frame
        if type(max_points) is not int or not 1 <= max_points <= 1000:
            raise ValueError("invalid trace limit")
        count = self._index
        limit = min(count, max_points)
        if not limit:
            return []
        # Include the current observation without exceeding the requested bound.
        indices = ({count - 1} if limit == 1 else
                   {i * (count - 1) // (limit - 1) for i in range(limit)})
        points = []
        segment = 0
        previous = None
        for index, payload in enumerate(self._frames[:count]):
            # Every consumed frame has already passed feed validation. Preserve
            # discontinuities even when downsampling omits transition frames.
            context = (payload["client_id"], payload["position"]["zone_id"], payload.get("instance_hint"),
                       payload["adapter"], payload["client_version"])
            if previous is not None and context != previous:
                segment += 1
            previous = context
            if index not in indices:
                continue
            snapshot = decode_frame(payload).snapshot
            p = snapshot.position
            points.append({"frame": index + 1, "zone_id": p.zone_id,
                           "instance_hint": snapshot.instance_hint, "segment": segment,
                           "x": p.x, "y": p.y, "z": p.z})
        return points

    def restart(self):
        return self.seek(1)

    def previous(self):
        if self._index <= 1:
            raise StopIteration("already at first recorded frame")
        return self.seek(self._index - 1)

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
