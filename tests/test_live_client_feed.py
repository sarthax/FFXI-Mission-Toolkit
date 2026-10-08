"""Offline tests for read-only live client telemetry feed."""
import unittest

from workbench.runtime.live_client.feed import TelemetryFeedAdapter
from workbench.runtime.live_client.models import DevelopmentAction
from workbench.runtime.live_client.service import LiveClientSession


def frame(timestamp=1.0, client="test-client"):
    return {
        "schema_version": 1,
        "client_id": client,
        "client_version": "fixture",
        "character": "Tester",
        "adapter": "offline-fixture",
        "observed_at": timestamp,
        "position": {"zone_id": 100, "x": 1, "y": 2, "z": 3, "heading": 0},
        "entities": [],
    }


class TelemetryFeedTests(unittest.TestCase):
    def test_read_only_session(self):
        adapter = TelemetryFeedAdapter("test-client")
        session = LiveClientSession(adapter, authorized_dev_session=True)
        with self.assertRaises(RuntimeError):
            session.observe()
        adapter.ingest(frame())
        self.assertEqual(session.observe().position.zone_id, 100)
        self.assertFalse(adapter.supports_writes)
        self.assertFalse(adapter.version_verified)
        with self.assertRaises(PermissionError):
            adapter.apply(DevelopmentAction, {})

    def test_reject_stale_duplicate_and_client_change_without_mutation(self):
        adapter = TelemetryFeedAdapter("test-client")
        adapter.ingest(frame(4))
        for candidate in (frame(4), frame(3), frame(5, "other")):
            with self.assertRaises(ValueError):
                adapter.ingest(candidate)
        self.assertEqual(adapter.snapshot().observed_at, 4)

    def test_decode_failure_does_not_replace_last_frame(self):
        adapter = TelemetryFeedAdapter("test-client")
        adapter.ingest(frame())
        broken = frame(2)
        broken["position"]["x"] = float("nan")
        with self.assertRaises(ValueError):
            adapter.ingest(broken)
        self.assertEqual(adapter.snapshot().observed_at, 1)
        self.assertEqual(adapter.entities(), ())


if __name__ == "__main__":
    unittest.main()
