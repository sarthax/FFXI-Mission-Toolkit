"""Explicit offline recording bootstrap for the read-only replay console.

Disabled unless the operator supplies both environment settings. Never scans
the filesystem or attaches to game processes.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .recording import load_recorded_frames
from .registry import ReplayRegistry


def register_configured_replay(registry: ReplayRegistry, config: Mapping[str, str]) -> bool:
    """Load a validated JSONL fixture and display its first frame on startup.

    Partial configuration is an error instead of silently choosing a client.
    Validation happens before the registry is modified.
    """
    recording = config.get("FFXI_LIVE_REPLAY_FILE", "").strip()
    client = config.get("FFXI_LIVE_REPLAY_CLIENT", "").strip()
    if not recording and not client:
        return False
    if not recording or not client:
        raise ValueError("both FFXI_LIVE_REPLAY_FILE and FFXI_LIVE_REPLAY_CLIENT are required")
    replay = load_recorded_frames(Path(recording), client_id=client)
    replay.advance()
    registry.add(client, replay)
    return True
