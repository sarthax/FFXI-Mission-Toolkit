"""Windows-compatible telemetry producer with explicit read-only observation sources.

The producer serializes observations supplied by a trusted adapter. No memory
offsets, process attach, injection, network listener, or game writes live here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .telemetry import decode_frame


class ObservationSource(Protocol):
    def observe(self) -> dict: ...


class TelemetryProducer:
    def __init__(self, destination: Path, client_id: str, source: ObservationSource):
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("invalid client ID")
        self.destination = Path(destination)
        self.client_id = client_id
        self.source = source
        self._last_timestamp: float | None = None

    def sample_once(self) -> float:
        """Validate an observation before atomically appending one JSONL line."""
        payload = self.source.observe()
        frame = decode_frame(payload)
        timestamp = frame.snapshot.observed_at
        if frame.snapshot.client_id != self.client_id:
            raise ValueError("observation belongs to another client")
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("stale observation")
        line = (json.dumps(payload, ensure_ascii=False, allow_nan=False,
                           separators=(",", ":")) + "\n").encode("utf-8")
        if len(line) > 65536:
            raise ValueError("observation exceeds file bridge line limit")
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        with self.destination.open("ab") as output:
            output.write(line)
            output.flush()
        self._last_timestamp = timestamp
        return timestamp
