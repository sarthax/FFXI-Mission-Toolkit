"""Viewer projection isolation and identity tests."""
import unittest

from workbench.runtime.live_client.telemetry import decode_frame
from workbench.runtime.live_client.viewer import viewer_projection


def payload():
    position = {"zone_id": 100, "x": 1, "y": 2, "z": 3, "heading": 0}
    return {"schema_version": 1, "client_id": "client-a",
            "client_version": "fixture", "character": "Tester",
            "observed_at": 10, "adapter": "fixture", "instance_hint": "A",
            "position": position, "entities": [
                {"client_index": 7, "kind": "npc", "name": "Guide",
                 "position": position, "server_entity_id": 123, "instance_hint": "A"},
                {"client_index": 9, "kind": "mob", "name": "Other instance",
                 "position": position, "instance_hint": "B"},
                {"client_index": 11, "kind": "player", "name": "Different zone",
                 "position": {**position, "zone_id": 101}},
            ]}


class ViewerProjectionTests(unittest.TestCase):
    def test_selected_instance_filters_entities(self):
        projection = viewer_projection(decode_frame(payload()), zone_id=100,
                                       client_id="client-a", instance_hint="A")
        self.assertTrue(projection["visible"])
        self.assertEqual(len(projection["entities"]), 1)
        self.assertEqual(projection["entities"][0]["server_entity_id"], 123)
        self.assertEqual(projection["player"]["position"]["x"], 1)

    def test_wrong_zone_client_or_instance_is_invisible(self):
        frame = decode_frame(payload())
        for kwargs in ({"zone_id": 99, "client_id": "client-a"},
                       {"zone_id": 100, "client_id": "client-b"},
                       {"zone_id": 100, "client_id": "client-a", "instance_hint": "B"}):
            projection = viewer_projection(frame, **kwargs)
            self.assertFalse(projection["visible"])
            self.assertIsNone(projection["player"])
            self.assertEqual(projection["entities"], [])

    def test_without_instance_selection_filters_zone_only(self):
        projection = viewer_projection(decode_frame(payload()), zone_id=100,
                                       client_id="client-a")
        self.assertEqual({item["client_index"] for item in projection["entities"]},
                         {7, 9})


if __name__ == "__main__":
    unittest.main()


def test_research_searches_use_reported_server_id_without_type_or_slot_guessing():
    from workbench.runtime.live_client.viewer import entity_research_links
    from urllib.parse import urlparse, parse_qs
    for absent in (None, 0, -1, True, '123', 0x100000000):
        assert entity_research_links(absent) == []
    for server_id in (123, 0xffffffff):
        links = entity_research_links(server_id)
        assert len(links) == 3
        assert [urlparse(link['href']).path for link in links] == ['/captures/search', '/entity', '/features/trace']
        for link in links:
            assert parse_qs(urlparse(link['href']).query)['q'] == [str(server_id)]
            assert link['basis'] == 'reported_server_id' and link['identity_verified'] is False
    projection = viewer_projection(decode_frame(payload()), zone_id=100, client_id='client-a')
    assert projection['entities'][0]['research_links'] == entity_research_links(123)
    assert projection['entities'][1]['research_links'] == []
    assert all('q=7' not in link['href'] for link in projection['entities'][0]['research_links'])
