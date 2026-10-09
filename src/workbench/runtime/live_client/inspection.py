"""Bounded local recording inspection for Live Client setup."""
from __future__ import annotations

import json
from pathlib import Path

from .recording import load_recorded_frames


def inspect_recording(path: str) -> dict:
    if not isinstance(path, str) or not path.strip() or len(path) > 2048:
        raise ValueError("enter a recording path")
    target = Path(path).expanduser()
    if not target.is_file():
        raise ValueError("recording file not found")
    with target.open("rb") as handle:
        first = handle.readline(65537)
    if len(first) > 65536:
        raise ValueError("first frame exceeds size limit")
    try:
        frame = json.loads(first.decode("utf-8-sig"))
        client_id = frame["client_id"]
    except (UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid first recording frame") from exc
    if not isinstance(client_id, str) or not client_id.strip():
        raise ValueError("invalid client ID")
    replay = load_recorded_frames(target, client_id=client_id)
    return {"client_id": client_id, "frames": replay.remaining,
            "valid": True, "read_only": True}
