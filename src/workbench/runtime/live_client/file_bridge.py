"""Explicit read-only, append-only telemetry file reader for a local client helper.

Transport only: the Windows-side helper must independently verify client
compatibility and produce schema-v1 JSON-lines. No process attachment here.
"""
from __future__ import annotations

import json
from pathlib import Path

from .feed import TelemetryFeedAdapter


class FileTelemetryBridge:
    """Poll only an operator-configured file, with strict bounded frames."""

    def __init__(self, path: Path, client_id: str, *, max_line_bytes: int = 65536):
        if type(max_line_bytes) is not int or not 1 <= max_line_bytes <= 1048576:
            raise ValueError("invalid line limit")
        self.path = Path(path)
        self.feed = TelemetryFeedAdapter(client_id)
        self.max_line_bytes = max_line_bytes
        self._offset = 0
        self._identity = None

    def poll(self, *, max_frames: int = 100) -> int:
        if type(max_frames) is not int or not 1 <= max_frames <= 1000:
            raise ValueError("invalid frame count")
        accepted = 0
        with self.path.open("rb") as stream:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self._identity is not None and (identity != self._identity or stat.st_size < self._offset):
                raise RuntimeError("telemetry feed was rotated or truncated; reconnect explicitly")
            self._identity = identity
            stream.seek(self._offset)
            for _ in range(max_frames):
                start = stream.tell()
                line = stream.readline(self.max_line_bytes + 1)
                if not line:
                    break
                if len(line) > self.max_line_bytes:
                    raise ValueError("telemetry line exceeds size limit")
                if not line.endswith(b"\n"):
                    stream.seek(start)
                    break  # Keep partial trailing frames for the next poll.
                try:
                    payload = json.loads(line.decode("utf-8"))
                    self.feed.ingest(payload)
                except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                    raise ValueError(f"invalid telemetry frame at byte {start}") from exc
                self._offset = stream.tell()
                accepted += 1
        return accepted
