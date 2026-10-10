"""Offline contract checks for the opt-in Wiki Ollama adapter."""
import io
import json
import os
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference import wiki_jobs, wiki_ollama_translate


class FakeResponse:
    def __enter__(self):
        return io.BytesIO(json.dumps({"response": "A key item costs 300 gil."}).encode())
    def __exit__(self, *args):
        return False


def test_model_translation_preserves_original_and_caches():
    with patch.dict(os.environ, {"WIKI_TRANSLATE_OLLAMA_MODEL": "test-jp-model"}):
        with patch.object(wiki_ollama_translate.urllib.request, "urlopen", return_value=FakeResponse()) as send:
            c = sqlite3.connect(":memory:")
            original = "だいじなものは300ギル。"
            one = wiki_jobs.translate_cached(c, "WikiWikiJP", "abc", "sha-a", original)
            assert one["status"] == "OK"
            assert one["unverified"] is True
            assert one["engine"] == "ollama:test-jp-model"
            assert one["warnings"] == []
            assert c.execute("SELECT translated FROM reference_wiki_translations").fetchone()[0] == one["text"]
            two = wiki_jobs.translate_cached(c, "WikiWikiJP", "abc", "sha-a", original)
            assert two["status"] == "OK"
            assert send.call_count == 1


def test_numeric_omission_warns():
    with patch.object(wiki_ollama_translate.urllib.request, "urlopen", return_value=FakeResponse()):
        result = wiki_ollama_translate.translate("レベル75", model="test")
        assert result["status"] == "OK"
        assert "75" in result["warnings"][0]


def test_refuse_nonlocal_and_oversize():
    try:
        wiki_ollama_translate.translate("test", model="test", url="https://example.com/api")
        assert False, "remote endpoint unexpectedly allowed"
    except ValueError:
        pass
    assert wiki_ollama_translate.translate("A" * 5001, model="test")["status"] == "ERROR"


if __name__ == "__main__":
    for key, test in sorted(globals().items()):
        if key.startswith("test_"):
            test()
            print("ok", key)
