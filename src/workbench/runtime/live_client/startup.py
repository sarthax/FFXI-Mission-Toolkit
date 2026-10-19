"""Best-effort local telemetry startup with observable configuration errors."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .bootstrap import register_configured_replay
from .configuration import effective_replay_configuration
from .file_bridge import FileTelemetryBridge
from .registry import ReplayRegistry


def initialize_live_client(registry: ReplayRegistry, settings: Mapping[str, str],
                           environment: Mapping[str, str]) -> str | None:
    """Never prevent the main GUI from starting due to a stale optional feed."""
    try:
        if settings.get("live_client_source") == "file_feed" and settings.get("live_client_auto_connect") == "1":
            path = settings.get("live_client_feed_file", "").strip()
            client = settings.get("live_client_feed_client", "").strip()
            if not path or not client:
                raise ValueError("file feed requires both file path and client ID")
            if not Path(path).is_file():
                raise FileNotFoundError("configured telemetry feed file does not exist")
            registry.add_feed(client, FileTelemetryBridge(Path(path), client))
            _add_headless_dir_feeds(registry, settings.get("headless_telemetry_dir", "").strip())
        else:
            register_configured_replay(registry, effective_replay_configuration(settings, environment))
    except (OSError, ValueError, PermissionError, RuntimeError) as exc:
        return f"Live Client unavailable: {exc}"
    return None


def _add_headless_dir_feeds(registry: ReplayRegistry, folder: str) -> None:
    """Register every <name>.jsonl in the headless telemetry dir as client xiheadless-<name> (multi-bot viewing)."""
    if not folder or not Path(folder).is_dir():
        return
    for feed in sorted(Path(folder).glob("*.jsonl")):
        client = f"xiheadless-{feed.stem.lower()}"
        if client in registry.client_ids():
            continue
        try:
            registry.add_feed(client, FileTelemetryBridge(feed, client))
        except (OSError, ValueError):
            continue
