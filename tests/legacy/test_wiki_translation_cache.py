"""Offline block-cache behavior tests; no installed Ollama required."""
import os
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference import wiki_translation_cache as cache

BLOCKS = [
    {"block_id": "a", "ordinal": 1, "block_type": "heading", "text": "報酬"},
    {"block_id": "hidden", "ordinal": 2, "block_type": "link", "text": "source link"},
    {"block_id": "b", "ordinal": 3, "block_type": "table_cell", "text": "100ギル"},
]


def fake(text, *, model, glossary=None):
    return {"status": "OK", "text": model + ":" + text, "warnings": []}


def test_cache_model_and_content_invalidation():
    db = sqlite3.connect(":memory:")
    with patch.object(cache.engine, "translate", side_effect=fake) as run:
        r = cache.translate_cached_blocks(db, source_id="WikiWikiJP", page_id="test",
                                          blocks=BLOCKS, model="jp-a")
        assert r["cache_misses"] == 2 and len(r["blocks"]) == 2
        assert cache.translate_cached_blocks(db, source_id="WikiWikiJP", page_id="test",
                                             blocks=BLOCKS, model="jp-a")["cache_hits"] == 2
        assert run.call_count == 2
        assert cache.translate_cached_blocks(db, source_id="WikiWikiJP", page_id="test",
                                             blocks=BLOCKS, model="jp-b")["cache_misses"] == 2
        changed = [dict(b) for b in BLOCKS]
        changed[0]["text"] = "新しい報酬"
        assert cache.translate_cached_blocks(db, source_id="WikiWikiJP", page_id="test",
                                             blocks=changed, model="jp-b")["cache_misses"] == 1
    assert db.execute("SELECT COUNT(*) FROM reference_wiki_block_translations").fetchone()[0] == 5


def test_partial_progress_is_reusable():
    db = sqlite3.connect(":memory:")
    calls = []

    def fail_second(text, *, model, glossary=None):
        calls.append(text)
        if len(calls) == 2:
            raise RuntimeError("simulated outage")
        return fake(text, model=model)

    with patch.object(cache.engine, "translate", side_effect=fail_second):
        first = cache.translate_cached_blocks(db, source_id="WikiWikiJP",
                                              page_id="retry", blocks=BLOCKS, model="jp-a")
    assert first["status"] == "ERROR"
    with patch.object(cache.engine, "translate", side_effect=fake) as run:
        result = cache.translate_cached_blocks(db, source_id="WikiWikiJP",
                                               page_id="retry", blocks=BLOCKS, model="jp-a")
        assert result["status"] == "OK" and result["cache_hits"] == 1
        assert run.call_count == 1


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
            print("ok", name)
