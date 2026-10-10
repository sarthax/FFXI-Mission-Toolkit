import sqlite3

from workbench.devtools.reference import wiki_client_term_index as idx


def _db(tmp_path):
    p = tmp_path / "t.db"
    con = sqlite3.connect(p)
    con.executescript("""
    CREATE TABLE auto_translate(cat_id,entry_id,key,category_en,category_ja,en,ja,ja_kana);
    CREATE TABLE items(item_id,category,name_en,name_ja,log_single_en,log_plural_en,desc_en,desc_ja);
    CREATE TABLE zones(zone_id,name);
    INSERT INTO auto_translate VALUES(1,1,'k','Places','',  'Home Point','ホームポイント','ほーむぽいんと');
    INSERT INTO items VALUES(1,'x','Potion','ポーション','','','','');
    """)
    con.commit()
    con.close()
    return p


def test_search_both_languages(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_CLIENT_TEXT_DB", str(_db(tmp_path)))
    for q in ("Home Point", "ホームポイント"):
        r = idx.search(q)
        assert r["status"] == "OK"
        assert r["results"][0]["en"] == "Home Point"
        assert r["results"][0]["ja"] == "ホームポイント"


def test_match_counts_terms(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_CLIENT_TEXT_DB", str(_db(tmp_path)))
    r = idx.match("ホームポイントでポーションを使う。ホームポイント")
    got = {t["ja"]: t["count"] for t in r["terms"]}
    assert got == {"ホームポイント": 2, "ポーション": 1}
