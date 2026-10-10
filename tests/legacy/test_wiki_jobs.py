#!/usr/bin/env python3
"""tests/legacy/test_wiki_jobs.py -- URL detection, temp->main merge, and no-engine translation for wiki_jobs.
No pytest dependency (matches the other tests/legacy scripts). Usage: py -3 tests/legacy/test_wiki_jobs.py"""
import os, sqlite3, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference import wiki_jobs


def test_detect_sources():
    assert wiki_jobs.detect("https://www.bg-wiki.com/ffxi/Lord_Asag") == ("BGWiki", "Lord Asag")
    assert wiki_jobs.detect("https://ffxiclopedia.fandom.com/wiki/Lord_Asag") == ("FFXIclopedia", "Lord Asag")
    assert wiki_jobs.detect("https://wikiwiki.jp/ffxi/%E3%83%B4%E3%82%A9%E3%82%A4%E3%83%89")[0] == "WikiWikiJP"
    assert wiki_jobs.detect("https://wikiwiki.jp/ffxi/") is None
    assert wiki_jobs.detect("https://example.com/x") is None


def test_merge_keeps_existing_rows():
    d = tempfile.mkdtemp()
    main, tmp = os.path.join(d, "m.db"), os.path.join(d, "t.db")
    for db, row in ((main, ("BGWiki", "1", "A", "a", "", "", "x", "h")), (tmp, ("WikiWikiJP", "T", "T", "T", "", "", "y", "h2"))):
        c = sqlite3.connect(db)
        c.execute(wiki_jobs._PAGES_DDL)
        c.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)", row)
        c.commit()
        c.close()
    assert wiki_jobs._merge(main, tmp, lambda m: None) == 1
    c = sqlite3.connect(main)
    assert c.execute("select count(*) from reference_wiki_pages").fetchone()[0] == 2
    c.close()


def test_translate_without_engine():
    os.environ.pop("WIKI_TRANSLATE_CMD", None)
    c = sqlite3.connect(":memory:")
    from unittest.mock import patch
    with patch("workbench.devtools.reference.wiki_ollama_translate.configured_model", return_value=""):
        assert wiki_jobs.translate_cached(c, "WikiWikiJP", "T", "h", "text")["status"] == "NO_ENGINE"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
