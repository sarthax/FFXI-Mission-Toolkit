"""Permanent Wiki merge failures must not be retried as SQLite locks."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as directory:
        destination=Path(directory)/"main.db"
        stage=Path(directory)/"stage.db"
        with sqlite3.connect(destination) as con:
            con.execute(wiki_jobs._PAGES_DDL)
        with sqlite3.connect(stage) as con:
            con.execute("CREATE TABLE unrelated(x INTEGER)")
        with patch.object(wiki_jobs.time,"sleep",side_effect=AssertionError("Unexpected retry")):
            try:
                wiki_jobs._merge(str(destination),str(stage),lambda message:None)
            except sqlite3.OperationalError as error:
                assert "reference_wiki_pages" in str(error),error
            else:
                raise AssertionError("Missing staging table was silently retried")
    print("Wiki permanent merge failure: PASS")

if __name__=="__main__":
    main()
