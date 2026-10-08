"""Read-only telemetry feed adapter for offline and future Windows bridge use.

The caller transports dictionaries; this adapter never discovers or controls a process.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ClientSnapshot, DevelopmentAction
from .telemetry import TelemetryFrame, decode_frame


@dataclass
class TelemetryFeedAdapter:
    """Accept validated frames for exactly one client, rejecting stale observations."""

    client_id: str
    _latest: TelemetryFrame | None = field(default=None, init=False, repr=False)

    @property
    def supports_writes(self) -> bool:
        return False

    @property
    def version_verified(self) -> bool:
        # A reported version string is not independent evidence of verification.
        return False

    def ingest(self, payload: dict) -> TelemetryFrame:
        frame = decode_frame(payload)
        if frame.snapshot.client_id != self.client_id:
            raise ValueError("telemetry client mismatch")
        if self._latest is not None and (
            frame.snapshot.observed_at <= self._latest.snapshot.observed_at
        ):
            raise ValueError("stale or duplicate telemetry frame")
        self._latest = frame
        return frame

    def snapshot(self) -> ClientSnapshot:
        if self._latest is None:
            raise RuntimeError("no telemetry received")
        return self._latest.snapshot

    def entities(self) -> tuple:
        if self._latest is None:
            return ()
        return self._latest.entities

    def apply(self, action: DevelopmentAction, parameters: dict) -> None:
        raise PermissionError("telemetry feed is read-only")
