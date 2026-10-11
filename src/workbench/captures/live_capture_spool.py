"""Bounded, read-only session spool for native live packet envelopes.

Transport-neutral reference implementation. The native callback must enqueue
without blocking and a separate worker must call drain(). No implicit threads.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import json
import os

from .live_capture_contract import LiveCaptureSequence, LivePacketEnvelope


class LiveCaptureSpool:
    def __init__(self, directory: Path, client_id: str, session_id: str, *,
                 queue_capacity: int = 512, segment_bytes: int = 4 * 1024 * 1024):
        if type(queue_capacity) is not int or not 1 <= queue_capacity <= 100000:
            raise ValueError("invalid queue capacity")
        if type(segment_bytes) is not int or segment_bytes < 16384:
            raise ValueError("invalid segment size")
        self.directory = Path(directory)
        self.client_id = client_id
        self.session_id = session_id
        self.queue_capacity = queue_capacity
        self.segment_bytes = segment_bytes
        self._queue = deque()
        self._sequence = LiveCaptureSequence()
        self._segment = 0
        self._size = 0
        self._file = None
        self._closed = False
        self._fault = None
        self.accepted = 0
        self.persisted = 0
        self.rejected = 0
        self.segments = []

    def enqueue(self, value: dict) -> bool:
        """Nonblocking bounded offer; caller must record false as source loss.

        Sequence numbers belong to the producer. Rejected packets MUST NOT be
        retried with reused sequence numbers; gaps are surfaced to consumers.
        """
        if self._closed or self._fault:
            return False
        packet = LivePacketEnvelope.from_mapping(value)
        if packet.client_id != self.client_id or packet.session_id != self.session_id:
            raise ValueError("wrong recording identity")
        if len(self._queue) >= self.queue_capacity:
            self.rejected += 1
            return False
        self._sequence.accept(packet)
        self._queue.append(value.copy())
        self.accepted += 1
        return True

    def _open_segment(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Exclusive create: a restart must never overwrite existing evidence.
        self._segment += 1
        name = f"segment-{self._segment:06d}.jsonl"
        path = self.directory / name
        self._file = path.open("xb")
        self.segments.append(str(path))
        self._size = 0

    def drain(self, limit: int = 256) -> int:
        """Blocking disk work; invoke from a worker, NEVER a packet callback."""
        if self._closed or self._fault:
            raise RuntimeError("spool stopped")
        if type(limit) is not int or limit < 1:
            raise ValueError("invalid drain limit")
        written = 0
        try:
            while self._queue and written < limit:
                line = (json.dumps(self._queue[0], separators=(",", ":"), sort_keys=True) + "\n").encode()
                if len(line) > self.segment_bytes:
                    raise ValueError("packet exceeds segment size")
                if self._file is None or self._size + len(line) > self.segment_bytes:
                    if self._file:
                        self._file.flush()
                        os.fsync(self._file.fileno())
                        self._file.close()
                    self._file = None
                    self._open_segment()
                self._file.write(line)
                self._size += len(line)
                self._queue.popleft()
                self.persisted += 1
                written += 1
            if self._file and written:
                self._file.flush()
                os.fsync(self._file.fileno())
        except (OSError, ValueError) as exc:
            self._fault = str(exc)
            raise
        return written

    def close(self):
        if self._closed:
            return
        try:
            while self._queue and not self._fault:
                self.drain()
        finally:
            if self._file:
                self._file.flush()
                os.fsync(self._file.fileno())
                self._file.close()
                self._file = None
            self._closed = True

    def health(self) -> dict:
        return {
            "client_id": self.client_id, "session_id": self.session_id,
            "queued": len(self._queue), "capacity": self.queue_capacity,
            "accepted": self.accepted, "persisted": self.persisted,
            "rejected": self.rejected, "segments": len(self.segments),
            "closed": self._closed, "fault": self._fault,
        }
