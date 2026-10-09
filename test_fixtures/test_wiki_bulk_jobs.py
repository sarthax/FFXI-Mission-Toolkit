"""Offline bounded Wiki batch checkpoint and UI regression."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from workbench.devtools.reference import wiki_bulk_jobs as bulk


def main():
    with tempfile.TemporaryDirectory() as directory:
        db=Path(directory)/"toolkit.db"
        assert bulk.status(db)==[]
        with patch.object(bulk.threading.Thread, "start"):
            job=bulk.start(db,50)
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT page_limit FROM wiki_bulk_jobs WHERE id=?",(job,)).fetchone()==(50,)
        bulk._RUNNING.clear()
        assert bulk.status(db)[0]["state"]=="interrupted"
        with patch.object(bulk.threading.Thread, "start"):
            bulk.resume(db,job)
        bulk._RUNNING.clear()
        bulk.pause(db,job)
        assert bulk.status(db)[0]["state"] in ("interrupted","pausing")
        try:
            bulk.start(db,999)
        except ValueError:
            pass
        else:
            raise AssertionError("unbounded batch was accepted")
    ui=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert 'id="wiki-bulk-start"' in ui
    assert "/wiki/bulk/start" in ui and "/wiki/bulk/resume" not in ui or "wiki/bulk/'+action" in ui
    print("Wiki batch checkpoints: PASS")


if __name__=="__main__":
    main()
