"""Wiki fetch errors must not silently look like missing articles."""
import json
from unittest.mock import patch
from workbench.devtools.reference import scrape_bg_wiki as bg
from workbench.devtools.reference import scrape_ffxiclopedia as fx


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def main():
    with patch.object(bg.urllib.request, "urlopen", return_value=Response({"error": {"code": "blocked"}})):
        try:
            bg._api_get({"action": "query"})
        except RuntimeError as exc:
            assert "blocked" in str(exc)
        else:
            raise AssertionError("BG API error was ignored")
    with patch.object(fx.urllib.request, "urlopen", return_value=Response({"error": {"code": "ratelimited"}})), patch.object(fx.time, "sleep"):
        try:
            fx.api(action="query")
        except RuntimeError as exc:
            assert "ratelimited" in str(exc)
        else:
            raise AssertionError("FFXIclopedia API error was ignored")
    print("Wiki scrape API errors: PASS")


if __name__ == "__main__":
    main()
