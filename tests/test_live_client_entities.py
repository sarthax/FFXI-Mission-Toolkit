import unittest

from workbench.runtime.live_client.entities import (
    EntityKind, EntityObservation, match_server_id, overlay_observations,
)
from workbench.runtime.live_client.models import Position


class EntityObservationTest(unittest.TestCase):
    def test_client_index_not_server_identity(self):
        entry = EntityObservation("a", 0x400, EntityKind.NPC, "Gwendy",
                                  Position(44, 1, 2, 3), 10)
        self.assertEqual(match_server_id([entry], 0x400), ())
        self.assertEqual(overlay_observations([entry], zone_id=44, client_id="a"), (entry,))

    def test_instance_fail_closed(self):
        entries = [
            EntityObservation("a", 1, EntityKind.MOB, "X", Position(44, 0, 0, 0), 1),
            EntityObservation("a", 2, EntityKind.MOB, "Y", Position(44, 0, 0, 0), 1,
                              instance_hint="instance-1"),
            EntityObservation("b", 3, EntityKind.MOB, "Z", Position(44, 0, 0, 0), 1,
                              instance_hint="instance-1"),
        ]
        self.assertEqual([x.name for x in overlay_observations(
            entries, zone_id=44, client_id="a", instance_hint="instance-1")], ["Y"])

    def test_server_identity_explicit(self):
        entry = EntityObservation("a", 123, EntityKind.NPC, "X",
                                  Position(44, 0, 0, 0), 1, server_entity_id=16900001)
        self.assertEqual(match_server_id([entry], 16900001), (entry,))


if __name__ == "__main__":
    unittest.main()
