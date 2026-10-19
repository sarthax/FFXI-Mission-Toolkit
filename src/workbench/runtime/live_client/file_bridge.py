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

    def skip_to_recent(self, keep_bytes: int = 262144) -> None:
        """On first attach to a long-running feed, start near the end instead of replaying history."""
        if self._offset != 0:
            return
        with self.path.open("rb") as stream:
            size = self.path.stat().st_size
            if size <= keep_bytes:
                return
            stream.seek(size - keep_bytes)
            stream.readline()  # discard the partial line so decoding starts on a frame boundary
            self._offset = stream.tell()

    def poll(self, *, max_frames: int = 100) -> int:
        if type(max_frames) is not int or not 1 <= max_frames <= 1000:
            raise ValueError("invalid frame count")
        accepted = 0
        with self.path.open("rb") as stream:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self._identity is not None and (identity != self._identity or stat.st_size < self._offset):
                # A new run recreates/truncates the file: restart from the top instead of failing forever.
                self._offset = 0
                self.feed._latest = None
                stream.close()
                return self.poll(max_frames=max_frames)
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
                except (ValueError, TypeError, KeyError, UnicodeError):
                    # Skip one bad frame; raising here without advancing wedged the feed permanently.
                    self._offset = stream.tell()
                    continue
                self._offset = stream.tell()
                accepted += 1
        return accepted
