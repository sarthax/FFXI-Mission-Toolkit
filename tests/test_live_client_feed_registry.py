"""Read-only file telemetry feed integration into the existing registry."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge
from workbench.runtime.live_client.registry import ReplayRegistry


def frame(t, client="a"):
    return {"schema_version": 1, "client_id": client, "client_version": "fixture",
            "character": "Hero", "adapter": "file", "observed_at": t,
            "position": {"zone_id": 100, "x": t, "y": 0, "z": 0, "heading": 90},
            "entities": []}


def test_file_feed_is_isolated_and_read_only():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "feed.jsonl"
        path.write_text(json.dumps(frame(1)) + "\n", encoding="utf-8")
        registry = ReplayRegistry()
        bridge = FileTelemetryBridge(path, "a")
        registry.add_feed("a", bridge)
        assert registry.client_ids() == ("a",)
        assert registry.status()[0]["observed"] is False
        assert registry.poll_feed("a") == 1
        assert registry.frame("a").snapshot.position.x == 1
        assert registry.status()[0]["source"] == "file_feed"
        assert registry.status()[0]["zone_id"] == 100
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(frame(2)) + "\n")
        assert registry.poll_feed("a") == 1
        assert registry.frame("a").snapshot.position.x == 2
        with pytest.raises(KeyError):
            registry.advance("a")
        with pytest.raises(ValueError):
            registry.add_feed("a", bridge)
        with pytest.raises(ValueError):
            registry.add_feed("b", bridge)
        registry.remove("a")
        assert registry.client_ids() == ()
