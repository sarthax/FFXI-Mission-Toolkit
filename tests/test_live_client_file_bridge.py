"""Offline tests for Windows-compatible read-only telemetry file transport."""
import json
import tempfile
import unittest
from pathlib import Path

from workbench.runtime.live_client.file_bridge import FileTelemetryBridge


def frame(t, client="c"):
    return {"schema_version": 1, "client_id": client, "client_version": "fixture",
            "character": "Hero", "adapter": "local-helper", "observed_at": t,
            "position": {"zone_id": 100, "x": t, "y": 0, "z": 0, "heading": 0},
            "entities": []}


class FileBridgeTests(unittest.TestCase):
    def test_append_and_partial_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.jsonl"
            first = json.dumps(frame(1)) + "\n"
            second = json.dumps(frame(2)) + "\n"
            path.write_bytes(first.encode() + second[:20].encode())
            bridge = FileTelemetryBridge(path, "c")
            self.assertEqual(bridge.poll(), 1)
            self.assertEqual(bridge.poll(), 0)
            with path.open("ab") as out:
                out.write(second[20:].encode())
            self.assertEqual(bridge.poll(), 1)
            self.assertEqual(bridge.feed.snapshot().position.x, 2)
            self.assertEqual(bridge.poll(), 0)

    def test_mismatch_and_truncation_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.jsonl"
            path.write_text(json.dumps(frame(1)) + "\n")
            bridge = FileTelemetryBridge(path, "c")
            self.assertEqual(bridge.poll(), 1)
            with path.open("a") as out:
                out.write(json.dumps(frame(2, "other")) + "\n")
            with self.assertRaises(ValueError):
                bridge.poll()
            self.assertEqual(bridge.feed.snapshot().observed_at, 1)
            path.write_text("")
            with self.assertRaises(RuntimeError):
                bridge.poll()

    def test_limit_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.jsonl"
            path.write_text(json.dumps(frame(1)) + "\n")
            bridge = FileTelemetryBridge(path, "c", max_line_bytes=100)
            with self.assertRaises(ValueError):
                bridge.poll()
            with self.assertRaises(ValueError):
                bridge.poll(max_frames=0)


if __name__ == "__main__":
    unittest.main()
