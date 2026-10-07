"""The Character Editor router must be mounted on the canonical Workbench app."""
import asyncio

from workbench.app import host


def _status(path: str) -> int:
    """GET `path` through the real ASGI app (no TestClient/httpx dependency); returns the HTTP status."""
    seen = {}

    async def run():
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
            "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8420")], "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8420),
        }
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.sleep(3600)

        async def send(message):
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]

        await host.app(scope, receive, send)

    asyncio.run(run())
    return seen["status"]


def test_character_editor_page_and_nested_routes_are_mounted():
    # app.routes only holds a lazy wrapper for included routers, so check the resolved route table.
    paths = host.app.openapi()["paths"]
    assert "/character-editor" in paths
    assert "/character-editor/status.json" in paths


def test_character_editor_page_is_not_404():
    assert _status("/character-editor") == 200
    assert _status("/character-editor/status.json") != 404


if __name__ == "__main__":
    test_character_editor_page_and_nested_routes_are_mounted()
    test_character_editor_page_is_not_404()
    print("Character Editor route registration self-test: PASS")
