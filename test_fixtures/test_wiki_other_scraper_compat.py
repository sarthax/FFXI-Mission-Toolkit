"""Offline coverage for modern FFXIclopedia revisions and JP anti-bot responses."""
import json
from unittest.mock import patch

from workbench.devtools.reference import scrape_ffxiclopedia as fx
from workbench.devtools.reference import scrape_wikiwiki_jp as jp


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.data


def main():
    for slot in ({"content": "Medusa article"}, {"*": "Medusa article"}):
        pages = {"query": {"pages": {"42": {
            "pageid": 42, "title": "Medusa",
            "revisions": [{"revid": 21, "timestamp": "2026-01-01", "slots": {"main": slot}}]
        }}}}
        with patch.object(fx, "api", return_value=pages):
            rows = list(fx.fetch(["Medusa"]))
        assert len(rows) == 1 and rows[0][-1] == "Medusa article", rows
    with patch.object(fx, "api", return_value={"query": {"pages": {"42": {
        "pageid": 42, "title": "Medusa", "revisions": [{"slots": {"main": {}}}]
    }}}}):
        try:
            list(fx.fetch(["Medusa"]))
        except RuntimeError as exc:
            assert "revision text unavailable" in str(exc)
        else:
            raise AssertionError("FFXIclopedia missing contents was ignored")
    with patch.object(jp.urllib.request, "urlopen", return_value=Response(b"<html><title>Just a moment...</title><body>cf-chl-</body></html>")):
        try:
            jp.get("Medusa")
        except RuntimeError as exc:
            assert "anti-bot challenge" in str(exc)
        else:
            raise AssertionError("Anti-bot page was accepted")
    print("Wiki other scraper compatibility: PASS")


if __name__ == "__main__":
    main()
