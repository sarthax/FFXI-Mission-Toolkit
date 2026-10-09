"""Scheduled FFXIclopedia refresh must defer while BG or JP jobs are active."""
import tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from workbench.devtools.reference import wiki_sync_coordination as shared
from workbench.devtools.reference import wiki_sync_schedule as schedule

def main():
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"wiki.db"
        schedule.configure(db,enabled=True,interval_hours=24,page_limit=50)
        with patch.object(shared.wiki_bg_dump_jobs,"_RUNNING",{"bg-job"}),patch.object(
             schedule.wiki_bulk_jobs,"start") as start:
            result=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=2))
            assert result["status"]=="busy" and result["running"][0]["source"]=="BGWiki",result
            start.assert_not_called()
        with patch.object(shared.wiki_jp_crawl_jobs,"_RUNNING",{"jp-job"}),patch.object(
             schedule.wiki_bulk_jobs,"start") as start:
            assert schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=2))["status"]=="busy"
            start.assert_not_called()
        with patch.object(schedule.wiki_bulk_jobs,"start",return_value="ffx-job") as start:
            assert schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=2))["status"]=="started"
            start.assert_called_once()
    print("Wiki cross-source scheduler guard: PASS")
if __name__=="__main__":main()
