"""Scheduled JP refresh is opt-in, bounded, and stops after a failed job."""
import tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from workbench.devtools.reference import wiki_jp_refresh_schedule as schedule
from workbench.devtools.reference import wiki_jp_crawl_jobs as jp

def main():
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        assert schedule.tick(db)["status"]=="disabled"
        schedule.configure(db,enabled=True,seed="クエスト",interval_hours=168,page_limit=50)
        with patch.object(jp,"start",return_value="jp-1") as start:
            r=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=2))
            assert r["status"]=="started",r
            start.assert_called_once_with(db,"クエスト",50,mode="refresh")
        with jp._db(db) as con:
            con.execute("""INSERT INTO wiki_jp_crawl_jobs
                (id,state,seed,page_limit,mode,queue_json) VALUES(?,?,?,?,?,?)""",
                ("jp-1","error","クエスト",50,"refresh",'["クエスト"]'))
        with patch.object(jp,"start") as start:
            r=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(days=8))
            assert r["status"]=="needs_attention",r
            start.assert_not_called()
        schedule.configure(db,enabled=False,seed="クエスト")
        assert schedule.tick(db)["status"]=="disabled"
    print("Japanese Wiki scheduled refresh safeguards: PASS")
if __name__=="__main__":main()
