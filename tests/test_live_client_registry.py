"""Multi-client read-only replay registry tests."""
import unittest

from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.replay import RecordedTelemetryReplay


def frame(client, timestamp):
    return {"schema_version": 1, "client_id": client, "client_version": "test",
            "character": "Tester", "adapter": "fixture", "observed_at": timestamp,
            "position": {"zone_id": 100, "x": 1, "y": 2, "z": 3, "heading": 0},
            "entities": []}


class RegistryTests(unittest.TestCase):
    def test_selection_and_independent_replay(self):
        registry = ReplayRegistry()
        registry.add("a", RecordedTelemetryReplay("a", [frame("a", 1)]))
        registry.add("b", RecordedTelemetryReplay("b", [frame("b", 2)]))
        self.assertEqual(registry.client_ids(), ("a", "b"))
        self.assertIsNone(registry.frame("b"))
        registry.advance("a")
        self.assertEqual(registry.frame("a").snapshot.client_id, "a")
        self.assertIsNone(registry.frame("b"))
        self.assertEqual(registry.status()[0]["remaining_frames"], 0)
        registry.remove("a")
        self.assertIsNone(registry.frame("a"))
        self.assertEqual(registry.client_ids(), ("b",))

    def test_no_duplicate_or_cross_client_registration(self):
        registry = ReplayRegistry()
        replay = RecordedTelemetryReplay("a", [frame("a", 1)])
        with self.assertRaises(ValueError):
            registry.add("b", replay)
        registry.add("a", replay)
        with self.assertRaises(ValueError):
            registry.add("a", replay)
        with self.assertRaises(KeyError):
            registry.advance("absent")


if __name__ == "__main__":
    unittest.main()
