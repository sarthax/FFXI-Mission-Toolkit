"""Portable JSON-lines telemetry replay regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from workbench.runtime.live_client.recording import load_recorded_frames


def frame(at, client="client-a", zone=100):
    return {"schema_version": 1, "client_id": client, "client_version": "offline",
            "character": "Tester", "adapter": "recorded",
            "observed_at": at, "position": {"zone_id": zone,
            "x": 1, "y": 2, "z": 3, "heading": 0}, "entities": []}


class RecordedJsonLinesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture.jsonl"

    def write(self, rows):
        self.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_round_trip_zone_transition(self):
        self.write([frame(1), frame(2, zone=200)])
        replay = load_recorded_frames(self.path, client_id="client-a")
        self.assertEqual(replay.remaining, 2)
        self.assertEqual(replay.advance().snapshot.position.zone_id, 100)
        self.assertEqual(replay.advance().snapshot.position.zone_id, 200)

    def test_wrong_client_and_order_rejected_early(self):
        for rows in ([frame(1), frame(2, client="other")],
                     [frame(2), frame(1)], [frame(1), frame(1)]):
            self.write(rows)
            with self.assertRaises(ValueError):
                load_recorded_frames(self.path, client_id="client-a")

    def test_bounds_invalid_data_and_empty(self):
        self.write([frame(1), frame(2)])
        with self.assertRaises(ValueError):
            load_recorded_frames(self.path, client_id="client-a", max_frames=1)
        with self.assertRaises(ValueError):
            load_recorded_frames(self.path, client_id="client-a", max_bytes=10)
        self.path.write_bytes(b"{not json}\n")
        with self.assertRaises(ValueError):
            load_recorded_frames(self.path, client_id="client-a")
        self.path.write_text("\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_recorded_frames(self.path, client_id="client-a")


if __name__ == "__main__":
    unittest.main()
