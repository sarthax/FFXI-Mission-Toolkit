"""Isolated replay-console browser route and observed-zone status tests."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay import RecordedTelemetryReplay
from workbench.runtime.live_client.replay_console import create_replay_console_router


class ReplayConsoleTests(unittest.TestCase):
    def test_console_and_projection_data(self):
        registry = ReplayRegistry()
        registry.add("test", RecordedTelemetryReplay("test", [{
            "schema_version": 1, "client_id": "test", "client_version": "fixture",
            "character": "Hero", "adapter": "offline", "observed_at": 2,
            "position": {"zone_id": 100, "x": 4, "y": 5, "z": 6, "heading": 7},
            "entities": [],
        }]))
        app = FastAPI()
        app.include_router(create_registry_router(registry))
        app.include_router(create_replay_console_router())
        client = TestClient(app)
        html = client.get("/live-client/replay/console")
        self.assertEqual(html.status_code, 200)
        self.assertIn("Live Client", html.text)
        self.assertIn("read-only", html.text.lower())
        self.assertEqual(client.get("/live-client/replay/clients").json()["clients"][0]["zone_id"], None)
        registry.advance("test")
        row = client.get("/live-client/replay/clients").json()["clients"][0]
        self.assertEqual(row["zone_id"], 100)
        projection = client.get("/live-client/replay/projection",
                                params={"client_id": "test", "zone_id": row["zone_id"]})
        self.assertEqual(projection.json()["player"]["position"]["heading"], 7)
        self.assertEqual(client.post("/live-client/replay/console").status_code, 405)


if __name__ == "__main__":
    unittest.main()
