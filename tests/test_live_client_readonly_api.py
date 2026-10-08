"""Live-client optional read-only router contracts."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.readonly_api import create_readonly_router
from workbench.runtime.live_client.telemetry import decode_frame


def frame(client="c1"):
    return decode_frame({
        "schema_version": 1, "client_id": client, "client_version": "fixture",
        "character": "Tester", "adapter": "offline", "observed_at": 1,
        "position": {"zone_id": 100, "x": 1, "y": 2, "z": 3, "heading": 4},
        "entities": [],
    })


class ReadOnlyApiTests(unittest.TestCase):
    def client(self, provider):
        app = FastAPI()
        app.include_router(create_readonly_router(provider))
        return TestClient(app)

    def test_projection_and_absent_client(self):
        client = self.client(lambda cid: frame() if cid == "c1" else None)
        response = client.get("/live-client/read-only/projection",
                              params={"client_id": "c1", "zone_id": 100})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["visible"])
        self.assertEqual(response.json()["player"]["position"]["heading"], 4)
        self.assertEqual(client.get("/live-client/read-only/projection",
                         params={"client_id": "missing", "zone_id": 100}).status_code, 404)

    def test_mismatched_provider_fails_closed(self):
        client = self.client(lambda cid: frame("other"))
        response = client.get("/live-client/read-only/projection",
                              params={"client_id": "c1", "zone_id": 100})
        self.assertEqual(response.status_code, 409)

    def test_validation_and_get_only(self):
        client = self.client(lambda cid: frame())
        endpoint = "/live-client/read-only/projection"
        self.assertEqual(client.get(endpoint, params={"client_id": "c1", "zone_id": -1}).status_code, 422)
        self.assertEqual(client.post(endpoint, json={}).status_code, 405)
        self.assertEqual(client.get(endpoint, params={"client_id": "c1", "zone_id": 101}).json()["visible"], False)


if __name__ == "__main__":
    unittest.main()
