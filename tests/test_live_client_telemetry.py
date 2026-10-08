import unittest
from workbench.runtime.live_client.telemetry import decode_frame


class TelemetryTest(unittest.TestCase):
    def setUp(self):
        self.packet = dict(schema_version=1, client_id="a", client_version="fixture",
                           character="Tester", adapter="test", observed_at=1.0,
                           position=dict(zone_id=44, x=1, y=2, z=3),
                           entities=[dict(client_index=1024, kind="npc", name="Example",
                                          position=dict(zone_id=44, x=4, y=5, z=6))])

    def test_read_only_frame(self):
        frame = decode_frame(self.packet)
        self.assertEqual(frame.snapshot.position.zone_id, 44)
        self.assertEqual(frame.entities[0].client_index, 1024)
        self.assertIsNone(frame.entities[0].server_entity_id)

    def test_nonfinite_and_bool_rejected(self):
        for bad in [float("nan"), float("inf"), True]:
            payload = {**self.packet, "observed_at": bad}
            with self.assertRaises(ValueError):
                decode_frame(payload)

    def test_inventory_scope_is_bounded_and_strict(self):
        for patch in ({"observation_scope": "invented"}, {"entities_truncated": 1},
                      {"observation_scope": "bounded_loaded_entities", "entities": self.packet["entities"] * 33}):
            with self.assertRaises(ValueError):
                decode_frame({**self.packet, **patch})
        frame = decode_frame({**self.packet, "observation_scope": "bounded_loaded_entities", "entities_truncated": True})
        self.assertTrue(frame.entities_truncated)
        self.assertEqual(frame.observation_scope, "bounded_loaded_entities")

    def test_entity_limit(self):
        with self.assertRaises(ValueError):
            decode_frame(self.packet, max_entities=0)

    def test_invalid_schema_and_client_id(self):
        for patch in ({"schema_version": 2}, {"client_id": ""}):
            with self.assertRaises(ValueError):
                decode_frame({**self.packet, **patch})


if __name__ == "__main__":
    unittest.main()
