"""Offline batch checkpoint tests, using cached JP page records only."""
import os
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__),"..","..","src"))
from workbench.devtools.reference import wiki_document
from workbench.devtools.reference import wiki_translation_batch as batch
from workbench.devtools.reference import wiki_translation_cache


def test_batch_completes_and_reuses_cache():
    with tempfile.TemporaryDirectory() as temp:
        db=os.path.join(temp,"wiki.db")
        with sqlite3.connect(db) as con:
            con.execute("""CREATE TABLE reference_wiki_pages
                (source_id TEXT,page_id TEXT,title TEXT)""")
            con.execute("INSERT INTO reference_wiki_pages VALUES('WikiWikiJP','p1','ミッション')")
            wiki_document.store_document(
                con,source_id="WikiWikiJP",page_id="p1",source_format="legacy_text",
                raw_source="報酬は100ギル",blocks=[{"block_id":"b1","ordinal":1,"block_type":"paragraph",
                    "text":"報酬は100ギル","heading_level":None,"section_path":None,"target":None,
                    "source_locator":None,"metadata":{}}])
        with patch.dict(os.environ,{"WIKI_TRANSLATE_OLLAMA_MODEL":"jp-test"}):
            with patch.object(wiki_translation_cache.engine,"translate",
                              return_value={"status":"OK","text":"Reward: 100 gil","warnings":[]}) as model:
                jid=batch.start(db,limit=10)
                for _ in range(100):
                    rows=batch.status(db)
                    if rows[0]["state"] in ("finished","interrupted"): break
                    time.sleep(.01)
                assert rows[0]["state"]=="finished",rows
                assert rows[0]["completed"]==1
                assert model.call_count==1
                second=batch.start(db,limit=10)
                for _ in range(100):
                    rows=batch.status(db)
                    if rows[0]["id"]==second and rows[0]["state"]=="finished":break
                    time.sleep(.01)
                assert rows[0]["state"]=="finished",rows
                assert model.call_count==1


if __name__=="__main__":
    test_batch_completes_and_reuses_cache()
    print("ok: batch checkpoint and cached repeat")
