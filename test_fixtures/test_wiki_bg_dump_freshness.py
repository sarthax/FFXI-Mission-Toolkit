"""BG local archive freshness follows its exact on-disk signature."""
import tempfile
from pathlib import Path
from workbench.devtools.reference import wiki_bg_dump_jobs as bg

def main():
    with tempfile.TemporaryDirectory() as temp:
        db=Path(temp)/"wiki.db"
        archive=Path(temp)/"bg.jsonl.gz"
        assert not bg.dump_refresh_status(db,archive)["available"]
        archive.write_bytes(b"snapshot one")
        initial=bg.dump_refresh_status(db,archive)
        assert initial["never_imported"] and not initial["changed"]
        with bg._db(db) as con:
            con.execute("""INSERT INTO wiki_bg_dump_jobs
                (id,state,dump_path,dump_signature,page_limit)
                VALUES(?,?,?,?,?)""",("one","completed",str(archive.resolve()),initial["signature"],50))
        assert not bg.dump_refresh_status(db,archive)["changed"]
        archive.write_bytes(b"snapshot changed and longer")
        assert bg.dump_refresh_status(db,archive)["changed"]
    print("BG local dump freshness: PASS")
if __name__=="__main__":main()
