"""Bounded, strict JSON-lines loading for offline live-client telemetry replay."""
from __future__ import annotations

import json
from pathlib import Path

from .replay import RecordedTelemetryReplay
from .telemetry import decode_frame


def load_recorded_frames(path: Path, *, client_id: str, max_frames: int = 10000,
                         max_bytes: int = 16 * 1024 * 1024) -> RecordedTelemetryReplay:
    """Validate every line before returning replay; never execute captured data."""
    if type(max_frames) is not int or not 1 <= max_frames <= 100000:
        raise ValueError("invalid frame limit")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 256 * 1024 * 1024:
        raise ValueError("invalid byte limit")
    if not isinstance(client_id, str) or not client_id.strip() or len(client_id) > 200:
        raise ValueError("invalid client ID")
    frames = []
    total = 0
    previous_time = None
    with Path(path).open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            total += len(raw)
            if total > max_bytes:
                raise ValueError("recording exceeds byte limit")
            if not raw.strip():
                continue
            if len(frames) >= max_frames:
                raise ValueError("recording exceeds frame limit")
            try:
                payload = json.loads(raw.decode("utf-8"))
                frame = decode_frame(payload)
            except (UnicodeError, ValueError, TypeError, KeyError) as error:
                raise ValueError(f"invalid telemetry at line {line_number}") from error
            if frame.snapshot.client_id != client_id:
                raise ValueError(f"client mismatch at line {line_number}")
            observed_at = frame.snapshot.observed_at
            if previous_time is not None and observed_at <= previous_time:
                raise ValueError(f"non-increasing timestamp at line {line_number}")
            previous_time = observed_at
            frames.append(payload)
    if not frames:
        raise ValueError("recording contains no frames")
    return RecordedTelemetryReplay(client_id, frames)
