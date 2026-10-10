"""Client-DAT terminology: ambiguity, longest-match, snapshot keying, cache integration."""
import os
import sqlite3
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference.wiki_translation_client_terms import ClientTerms
from workbench.devtools.reference import wiki_translation_cache as cache, wiki_ollama_translate as engine


def make_db(path, fire_sha="a"):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE items(item_id INT, name_ja TEXT, name_en TEXT);
    CREATE TABLE auto_translate(ja TEXT, en TEXT);
    CREATE TABLE dat_pairs(kind TEXT, ident TEXT, en_sha1 TEXT, ja_sha1 TEXT);
    INSERT INTO items VALUES(1,'炎のクリスタル','Fire Crystal');
    INSERT INTO items VALUES(2,'炎のクリスタルの欠片','Fire Crystal Shard');
    INSERT INTO items VALUES(3,'同名アイテム','Twin A');
    INSERT INTO items VALUES(4,'同名アイテム','Twin B');
    INSERT INTO items VALUES(5,'水','Water');
    INSERT INTO auto_translate VALUES('初めまして。','Nice to meet you.');
    """)
    con.execute("INSERT INTO dat_pairs VALUES('items','0',?,'j')", (fire_sha,))
    con.commit(); con.close()


def test_terms_and_snapshot():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.db"); make_db(db)
        ct = ClientTerms(db)
        t = ct.terms_in("炎のクリスタルの欠片を集める。同名アイテムと水。")
        assert t == {"炎のクリスタルの欠片": "Fire Crystal Shard"}, t  # longest wins, ambiguous & short dropped
        assert ct.terms_in("初めまして。") == {"初めまして。": "Nice to meet you."}
        db2 = os.path.join(d, "t2.db"); make_db(db2, fire_sha="b")
        assert ct.snapshot_id != ClientTerms(db2).snapshot_id
        assert ClientTerms(os.path.join(d, "nope.db")).snapshot_id == "none"
        assert ClientTerms(os.path.join(d, "nope.db")).terms_in("炎のクリスタル") == {}


def test_cache_uses_client_terms_and_keys_on_snapshot():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "t.db"); make_db(db)
        seen = []
        orig = engine.translate
        engine.translate = lambda text, **kw: (seen.append(kw["glossary"]) or
                                               {"status": "OK", "text": "Fire Crystal", "warnings": []})
        try:
            con = sqlite3.connect(":memory:")
            blocks = [{"block_id": "b1", "block_type": "paragraph", "text": "炎のクリスタル"}]
            kw = dict(source_id="WikiWikiJP", page_id="1", blocks=blocks, model="m")
            r1 = cache.translate_cached_blocks(con, client_terms=ClientTerms(db), **kw)
            assert r1["cache_misses"] == 1 and seen[-1].get("炎のクリスタル") == "Fire Crystal"
            r2 = cache.translate_cached_blocks(con, client_terms=ClientTerms(db), **kw)
            assert r2["cache_hits"] == 1
            db2 = os.path.join(d, "t2.db"); make_db(db2, fire_sha="b")
            r3 = cache.translate_cached_blocks(con, client_terms=ClientTerms(db2), **kw)
            assert r3["cache_misses"] == 1  # new client snapshot invalidates drafts
        finally:
            engine.translate = orig


if __name__ == "__main__":
    test_terms_and_snapshot(); test_cache_uses_client_terms_and_keys_on_snapshot()
    print("ok: client terms")
