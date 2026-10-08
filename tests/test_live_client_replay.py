"""Offline replay and health lifecycle regressions."""
import unittest

from workbench.runtime.live_client.replay import (
    ConnectionState, RecordedTelemetryReplay,
)


def frame(at, client="client-a", zone=1):
    return {
        "schema_version": 1, "client_id": client, "client_version": "fixture",
        "character": "Tester", "adapter": "recorded-test", "observed_at": at,
        "position": {"zone_id": zone, "x": 1, "y": 2, "z": 3, "heading": 0},
        "entities": [],
    }


class RecordedReplayTests(unittest.TestCase):
    def test_multi_frame_lifecycle(self):
        replay = RecordedTelemetryReplay("client-a", [frame(10), frame(12, zone=2)])
        self.assertEqual(replay.health(now=10).state, ConnectionState.DISCONNECTED)
        replay.advance()
        self.assertEqual(replay.health(now=11).state, ConnectionState.CONNECTED)
        replay.advance()
        self.assertEqual(replay.feed.snapshot().position.zone_id, 2)
        self.assertEqual(replay.health(now=20).state, ConnectionState.STALE)
        self.assertEqual(replay.health(now=20).frame_count, 2)
        self.assertEqual(replay.remaining, 0)
        with self.assertRaises(StopIteration):
            replay.advance()

    def test_invalid_frame_is_not_consumed(self):
        replay = RecordedTelemetryReplay("client-a", [frame(10), frame(11, client="wrong")])
        replay.advance()
        with self.assertRaises(ValueError):
            replay.advance()
        self.assertEqual(replay.remaining, 1)
        self.assertEqual(replay.feed.snapshot().observed_at, 10)

    def test_clock_and_age_validation(self):
        replay = RecordedTelemetryReplay("client-a", [frame(10)])
        replay.advance()
        for kwargs in ({"now": float("nan")}, {"now": 10, "max_age": -1},
                       {"now": 10, "max_age": float("inf")}):
            with self.assertRaises(ValueError):
                replay.health(**kwargs)
        self.assertEqual(replay.health(now=9).state, ConnectionState.STALE)


if __name__ == "__main__":
    unittest.main()
