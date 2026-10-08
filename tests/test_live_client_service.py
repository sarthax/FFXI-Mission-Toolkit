"""Offline replay and waypoint contract tests (no Windows client necessary)."""
import unittest

from workbench.runtime.live_client import ClientSnapshot, DevelopmentAction, Position, Waypoint
from workbench.runtime.live_client.service import LiveClientSession, ReplayAdapter
from workbench.runtime.live_client.waypoints import parse_waypoints, waypoint_document, path_document


class LiveClientServiceTest(unittest.TestCase):
    def setUp(self):
        self.frames = [
            ClientSnapshot("client-1", "fixture", "Tester", Position(44, 1, 2, 3), 1.0, "replay"),
            ClientSnapshot("client-1", "fixture", "Tester", Position(44, 4, 5, 6), 2.0, "replay"),
        ]

    def test_replay_capture(self):
        adapter = ReplayAdapter(self.frames)
        session = LiveClientSession(adapter)
        session.record_sample()
        adapter.advance()
        session.record_sample()
        self.assertEqual([s.position.x for s in session.recorded_path()], [1, 4])
        self.assertEqual(path_document(list(session.recorded_path()))["schema_version"], 1)

    def test_write_denied_even_when_opted_in(self):
        session = LiveClientSession(ReplayAdapter(self.frames), authorized_dev_session=True)
        with self.assertRaises(PermissionError):
            session.execute(DevelopmentAction.NUDGE, {"x": 1})

    def test_waypoint_round_trip(self):
        original = [Waypoint("Port", Position(44, 2, 3, 4))]
        self.assertEqual(parse_waypoints(waypoint_document(original)), original)

    def test_malformed_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_waypoints({"schema_version": 2, "kind": "live_client_waypoints", "waypoints": []})


if __name__ == "__main__":
    unittest.main()
