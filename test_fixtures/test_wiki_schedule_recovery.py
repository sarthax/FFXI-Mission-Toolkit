"""Checkpointed scheduled Wiki job recovers after restart without duplicate job."""
import json, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from workbench.devtools.reference import wiki_bulk_jobs as batch
from workbench.devtools.reference import wiki_sync_schedule as schedule

def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"wiki.db"
        schedule.configure(db,enabled=True,interval_hours=6,page_limit=50)
        with batch._connect(db) as con:
            con.execute("""INSERT INTO wiki_bulk_jobs(id,source,state,mode,page_limit,
                         pending_json,processed) VALUES(?,?,?,?,?,?,?)""",
                        ("recovery1","FFXIclopedia","running","changed",50,
                         json.dumps(["Medusa","Japanese article"]),5))
        with schedule._db(db) as con:
            con.execute("UPDATE wiki_sync_schedule SET last_job_id=? WHERE source='FFXIclopedia'",("recovery1",))
        assert batch.recover_interrupted(db)==1
        assert batch.latest_recoverable(db,job_id="recovery1")["pending"]==2
        with patch.object(batch.threading.Thread,"start"),patch.object(batch,"start") as fresh:
            result=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(seconds=2))
            assert result=={"status":"resumed","job_id":"recovery1"},result
            fresh.assert_not_called()
        assert batch.status(db)[0]["state"]=="queued"
        batch._RUNNING.clear()
        with batch._connect(db) as con:
            con.execute("UPDATE wiki_bulk_jobs SET state='paused' WHERE id='recovery1'")
        with patch.object(batch,"start") as fresh:
            result=schedule.tick(db,now=datetime.now(timezone.utc)+timedelta(hours=7))
            assert result["status"]=="needs_attention",result
            fresh.assert_not_called()
        schedule.configure(db,enabled=False,interval_hours=24,page_limit=50)
        assert schedule.tick(db)["status"]=="disabled"
    print("Wiki scheduled checkpoint recovery: PASS")

if __name__=="__main__":
    main()
