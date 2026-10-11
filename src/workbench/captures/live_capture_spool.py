"""Bounded, read-only session spool for native live packet envelopes.

Transport-neutral reference implementation. The native callback must enqueue
without blocking and a separate worker must call drain(). No implicit threads.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Lock
import json
import os
import hashlib

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
        self._lock = Lock()
        self._drain_lock = Lock()
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
        self._ranges = []
        self._first_seq = None
        self._last_seq = None

    def enqueue(self, value: dict) -> bool:
        """Nonblocking bounded offer; caller must record false as source loss.

        Sequence numbers belong to the producer. Rejected packets MUST NOT be
        retried with reused sequence numbers; gaps are surfaced to consumers.
        """
        packet = LivePacketEnvelope.from_mapping(value)
        if packet.client_id != self.client_id or packet.session_id != self.session_id:
            raise ValueError("wrong recording identity")
        # Callback-side offer never waits for the disk worker lock.
        if not self._lock.acquire(blocking=False):
            self.rejected += 1
            return False
        try:
            if self._closed or self._fault or len(self._queue) >= self.queue_capacity:
                self.rejected += 1
                return False
            self._sequence.accept(packet)
            self._queue.append(value.copy())
            self.accepted += 1
            return True
        finally:
            self._lock.release()

    def _open_segment(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Exclusive create: a restart must never overwrite existing evidence.
        self._segment += 1
        name = f"segment-{self._segment:06d}.jsonl"
        path = self.directory / name
        self._file = path.open("xb")
        self.segments.append(str(path))
        self._size = 0
        self._first_seq = None
        self._last_seq = None

    def drain(self, limit: int = 256) -> int:
        """Blocking disk work; invoke from a worker, NEVER a packet callback."""
        if self._closed or self._fault:
            raise RuntimeError("spool stopped")
        if type(limit) is not int or limit < 1:
            raise ValueError("invalid drain limit")
        if not self._drain_lock.acquire(blocking=False):
            raise RuntimeError("concurrent drain is not supported")
        written = 0
        try:
            while written < limit:
                with self._lock:
                    if not self._queue:
                        break
                    current = self._queue[0]
                line = (json.dumps(current, separators=(",", ":"), sort_keys=True) + "\n").encode()
                if len(line) > self.segment_bytes:
                    raise ValueError("packet exceeds segment size")
                if self._file is None or self._size + len(line) > self.segment_bytes:
                    if self._file:
                        self._file.flush()
                        os.fsync(self._file.fileno())
                        self._file.close()
                        self._ranges.append((self.segments[-1], self._first_seq, self._last_seq))
                    self._file = None
                    self._open_segment()
                self._file.write(line)
                self._file.flush()
                os.fsync(self._file.fileno())
                self._size += len(line)
                with self._lock:
                    self._queue.popleft()
                if self._first_seq is None:
                    self._first_seq = current["sequence"]
                self._last_seq = current["sequence"]
                self.persisted += 1
                written += 1
        except (OSError, ValueError) as exc:
            self._fault = str(exc)
            raise
        finally:
            self._drain_lock.release()
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
                self._ranges.append((self.segments[-1], self._first_seq, self._last_seq))
                self._file = None
            self._closed = True
            if not self._fault and self._ranges:
                entries = []
                for name, first, last in self._ranges:
                    entries.append({"filename": Path(name).name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest(), "first_sequence": first, "last_sequence": last})
                manifest = {"schema_version": 1, "client_id": self.client_id, "session_id": self.session_id, "segments": entries}
                target = self.directory / "manifest.json"
                if target.exists():
                    raise FileExistsError(f"manifest already exists: {target}")
                temp = self.directory / "manifest.json.tmp"
                try:
                    with temp.open("x", encoding="utf-8") as stream:
                        json.dump(manifest, stream, sort_keys=True)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(temp, target)  # exclusive, atomic publication
                finally:
                    temp.unlink(missing_ok=True)

    def health(self) -> dict:
        return {
            "client_id": self.client_id, "session_id": self.session_id,
            "queued": len(self._queue), "capacity": self.queue_capacity,
            "accepted": self.accepted, "persisted": self.persisted,
            "rejected": self.rejected, "segments": len(self.segments),
            "closed": self._closed, "fault": self._fault,
        }


def inspect_interrupted_session(directory: Path) -> dict:
    """Read-only diagnostic for an unfinalized spool; never repairs evidence in place."""
    directory = Path(directory)
    result = {"status": "missing", "segments": 0, "packets": 0, "errors": []}
    if not directory.is_dir():
        return result
    manifest = directory / "manifest.json"
    if manifest.exists():
        try:
            from .live_capture_jsonl import parse_manifest
            client_id, session_id, entries = parse_manifest(manifest.read_bytes())
            payloads = []
            for entry in entries:
                segment = directory / entry["filename"]
                data = segment.read_bytes()
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise ValueError(f"native segment checksum mismatch: {entry['filename']}")
                payloads.append(data)
            from .live_capture_jsonl import parse_segments
            parsed = parse_segments(payloads)
            for entry, rows in zip(entries, parsed):
                if not rows or rows[0][0].sequence != entry["first_sequence"] or rows[-1][0].sequence != entry["last_sequence"]:
                    raise ValueError("native segment sequence range mismatch")
                if any(packet.client_id != client_id or packet.session_id != session_id for packet, *_ in rows):
                    raise ValueError("native segment identity mismatch")
            result["segments"] = len(entries)
            result["packets"] = sum(len(rows) for rows in parsed)
            result["status"] = "verified_complete"
        except (OSError, ValueError) as exc:
            result["status"] = "invalid_manifest"
            result["errors"].append(str(exc))
        return result
    result["status"] = "interrupted"
    from .live_capture_jsonl import parse_segments
    segments = sorted(directory.glob("segment-*.jsonl"))
    result["segments"] = len(segments)
    if not segments:
        result["status"] = "empty"
        return result
    try:
        payloads = [path.read_bytes() for path in segments]
        parsed = parse_segments(payloads)
        result["packets"] = sum(len(rows) for rows in parsed)
        result["status"] = "recoverable_unfinalized"
    except (OSError, ValueError) as exc:
        result["status"] = "damaged_unfinalized"
        result["errors"].append(str(exc))
    return result
