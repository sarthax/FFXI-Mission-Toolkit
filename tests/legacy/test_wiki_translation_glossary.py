"""Reviewed-only glossary extraction regression tests."""
import sqlite3
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from workbench.devtools.reference.wiki_translation_glossary import reviewed_glossary


def test_reviewed_topics_only():
    con=sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE reference_wiki_pages(source_id TEXT,page_id TEXT,title TEXT);
    CREATE TABLE reference_wiki_topics(topic_id TEXT,canonical_title TEXT);
    CREATE TABLE reference_wiki_topic_pages(topic_id TEXT,source_id TEXT,page_id TEXT,link_method TEXT);
    INSERT INTO reference_wiki_pages VALUES('WikiWikiJP','1','だいじなもの');
    INSERT INTO reference_wiki_pages VALUES('WikiWikiJP','2','ミッション');
    INSERT INTO reference_wiki_topics VALUES('a','Key Item');
    INSERT INTO reference_wiki_topics VALUES('b','Mission');
    INSERT INTO reference_wiki_topic_pages VALUES('a','WikiWikiJP','1','MANUAL');
    INSERT INTO reference_wiki_topic_pages VALUES('b','WikiWikiJP','2','AUTOMATIC');
    """)
    assert reviewed_glossary(con)=={"だいじなもの":"Key Item"}
    con.execute("INSERT INTO reference_wiki_topics VALUES('c','Different Item')")
    con.execute("INSERT INTO reference_wiki_topic_pages VALUES('c','WikiWikiJP','1','MANUAL')")
    assert reviewed_glossary(con)=={}


if __name__=="__main__":
    test_reviewed_topics_only()
    print("ok: reviewed glossary extraction")
