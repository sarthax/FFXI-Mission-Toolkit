"""Disabled-by-default Wiki scheduler, persisted settings, bounded due launches."""
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_sync_schedule as schedule

def main():
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"wiki.db"
        assert schedule.settings(db)["enabled"]==0
        with patch.object(schedule.wiki_bulk_jobs,"start") as begin:
            assert schedule.tick(db)["status"]=="disabled"
            begin.assert_not_called()
            config=schedule.configure(db,enabled=True,interval_hours=6,page_limit=50)
            assert config["enabled"]==1 and config["interval_hours"]==6
            begin.return_value="scheduled1"
            launched=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=1))
            assert launched=={"status":"started","job_id":"scheduled1"},launched
            begin.assert_called_once_with(db,50,mode="changed")
            assert schedule.tick(db)["status"]=="not_due"
            assert schedule.settings(db)["last_job_id"]=="scheduled1"
            schedule.configure(db,enabled=False,interval_hours=24,page_limit=50)
            assert schedule.tick(db)["status"]=="disabled"
        try:
            schedule.configure(db,enabled=True,interval_hours=1,page_limit=50)
        except ValueError: pass
        else: raise AssertionError("Unsupported interval accepted")
        with patch.object(schedule.wiki_bulk_jobs,"start",side_effect=ValueError("Missing cache")):
            schedule.configure(db,enabled=True,interval_hours=24,page_limit=50)
            failure=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=1))
            assert failure["status"]=="error" and "Missing cache" in failure["error"]
            assert "Missing cache" in schedule.settings(db)["last_error"]
    print("Wiki opt-in scheduling: PASS")

if __name__=="__main__":main()
