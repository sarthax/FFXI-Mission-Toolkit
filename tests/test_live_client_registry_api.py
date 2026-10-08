"""Optional replay registry HTTP API contract tests."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay import RecordedTelemetryReplay


def frame(client, timestamp):
    return {"schema_version": 1, "client_id": client, "client_version": "fixture",
            "character": "Tester", "adapter": "offline", "observed_at": timestamp,
            "position": {"zone_id": 100, "x": 5, "y": 6, "z": 7, "heading": 8},
            "entities": []}


class RegistryApiTests(unittest.TestCase):
    def setUp(self):
        self.registry = ReplayRegistry()
        self.registry.add("a", RecordedTelemetryReplay("a", [frame("a", 1)]))
        self.registry.add("b", RecordedTelemetryReplay("b", [frame("b", 2)]))
        app = FastAPI()
        app.include_router(create_registry_router(self.registry))
        self.client = TestClient(app)

    def test_list_and_select_client(self):
        result = self.client.get("/live-client/replay/clients")
        self.assertEqual(result.status_code, 200)
        self.assertEqual([row["client_id"] for row in result.json()["clients"]], ["a", "b"])
        endpoint = "/live-client/replay/projection"
        self.assertEqual(self.client.get(endpoint, params={"client_id": "a", "zone_id": 100}).status_code, 409)
        self.registry.advance("a")
        response = self.client.get(endpoint, params={"client_id": "a", "zone_id": 100})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["player"]["position"]["x"], 5)
        self.assertEqual(self.client.get(endpoint, params={"client_id": "b", "zone_id": 100}).status_code, 409)

    def test_missing_bad_input_and_get_only(self):
        endpoint = "/live-client/replay/projection"
        self.assertEqual(self.client.get(endpoint, params={"client_id": "missing", "zone_id": 100}).status_code, 404)
        self.assertEqual(self.client.get(endpoint, params={"client_id": "a", "zone_id": -1}).status_code, 422)
        self.assertEqual(self.client.post("/live-client/replay/clients", json={}).status_code, 405)
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 405)


if __name__ == "__main__":
    unittest.main()
