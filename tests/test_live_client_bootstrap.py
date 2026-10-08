"""Explicit read-only replay bootstrap regressions."""
import json
import tempfile
import unittest
from pathlib import Path

from workbench.runtime.live_client.bootstrap import register_configured_replay
from workbench.runtime.live_client.registry import ReplayRegistry


class BootstrapTests(unittest.TestCase):
    def test_disabled_and_partial_configuration(self):
        registry = ReplayRegistry()
        self.assertFalse(register_configured_replay(registry, {}))
        self.assertEqual(registry.client_ids(), ())
        for config in ({"FFXI_LIVE_REPLAY_CLIENT": "demo"},
                       {"FFXI_LIVE_REPLAY_FILE": "record.jsonl"}):
            with self.assertRaises(ValueError):
                register_configured_replay(registry, config)

    def test_fixture_loads_first_frame_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.jsonl"
            def frame(t):
                return {"schema_version": 1, "client_id": "demo",
                        "client_version": "offline", "character": "Hero",
                        "adapter": "fixture", "observed_at": t,
                        "position": {"zone_id": 100, "x": t, "y": 0, "z": 0, "heading": 0},
                        "entities": []}
            path.write_text("\n".join(json.dumps(frame(t)) for t in (1, 2)), encoding="utf-8")
            registry = ReplayRegistry()
            configured = {"FFXI_LIVE_REPLAY_FILE": str(path),
                          "FFXI_LIVE_REPLAY_CLIENT": "demo"}
            self.assertTrue(register_configured_replay(registry, configured))
            self.assertEqual(registry.frame("demo").snapshot.position.x, 1)
            self.assertEqual(registry.status()[0]["remaining_frames"], 1)
            with self.assertRaises(ValueError):
                register_configured_replay(registry, configured)

    def test_invalid_recording_does_not_register(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text("{broken", encoding="utf-8")
            registry = ReplayRegistry()
            with self.assertRaises(ValueError):
                register_configured_replay(registry, {
                    "FFXI_LIVE_REPLAY_FILE": str(path),
                    "FFXI_LIVE_REPLAY_CLIENT": "demo",
                })
            self.assertEqual(registry.client_ids(), ())


if __name__ == "__main__":
    unittest.main()
