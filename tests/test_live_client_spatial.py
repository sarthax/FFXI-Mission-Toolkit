import unittest

from workbench.runtime.live_client.models import PathSample, Position, Waypoint
from workbench.runtime.live_client.spatial import (nearby_waypoints, placement_from_sample,
                                                   split_path_by_zone)


class LiveClientSpatialTest(unittest.TestCase):
    def test_nearby_only_same_zone(self):
        current = Position(44, 0, 0, 0)
        points = [Waypoint("elsewhere", Position(45, 0, 0, 0)),
                  Waypoint("close", Position(44, 3, 4, 0)),
                  Waypoint("far", Position(44, 20, 0, 0))]
        self.assertEqual([(w.name, d) for w, d in nearby_waypoints(current, points, 5)],
                         [("close", 5)])

    def test_place_is_proposal_only(self):
        sample = PathSample(1.5, Position(44, 1, 2, 3, 90), "client-a")
        result = placement_from_sample("npc", sample)
        self.assertEqual((result.entity_kind, result.position.heading), ("npc", 90))
        with self.assertRaises(ValueError):
            placement_from_sample("player", sample)

    def test_zone_and_client_boundaries(self):
        samples = [PathSample(i, Position(zone, 0, 0, 0), client)
                   for i, zone, client in [(1, 44, "a"), (2, 44, "a"),
                                           (3, 45, "a"), (4, 45, "b")]]
        self.assertEqual([len(x) for x in split_path_by_zone(samples)], [2, 1, 1])


if __name__ == "__main__":
    unittest.main()
