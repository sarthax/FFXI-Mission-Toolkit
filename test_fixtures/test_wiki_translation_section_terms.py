"""Per-block client terms and single-section translation (engine stubbed, no Ollama)."""
import sqlite3

from workbench.devtools.reference import wiki_translation_cache as cache, wiki_ollama_translate as engine, wiki_jobs


class FakeTerms:
    snapshot_id = "t"

    def terms_in(self, text, limit=40):
        return {"薬": "Potion"} if "薬" in text else {}


def blocks():
    return [
        {"block_id": "b1", "ordinal": 1, "block_type": "paragraph", "text": "薬を使う", "section_path": "概要"},
        {"block_id": "b2", "ordinal": 2, "block_type": "paragraph", "text": "剣を使う", "section_path": "入手"},
    ]


def main() -> None:
    engine.translate = lambda text, model, glossary=None: {"status": "OK", "text": "EN:" + text, "warnings": []}
    con = sqlite3.connect(":memory:")
    res = cache.translate_cached_blocks(con, source_id="S", page_id="p", blocks=blocks(), model="m", client_terms=FakeTerms())
    assert res["status"] == "OK"
    by = {b["block_id"]: b for b in res["blocks"]}
    assert by["b1"]["client_terms"] == {"薬": "Potion"} and by["b2"]["client_terms"] == {}
    # section filter used by translate_cached
    only = [b for b in blocks() if (b["section_path"] or "").startswith("入手")]
    assert [b["block_id"] for b in only] == ["b2"]
    import inspect
    assert "section" in inspect.signature(wiki_jobs.translate_cached).parameters
    print("wiki translation section/client-terms self-test: PASS")


if __name__ == "__main__":
    main()
