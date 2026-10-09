"""A scrape is done only when the imported page is visible in the main cache."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from workbench.devtools.reference import wiki_jobs


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "main.db"
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
        row = ("BGWiki", "123", "Medusa", "medusa", "7", "2026-01-01", "Some wiki text", "hash")
        item = {"row": row, "source_format": "mediawiki", "raw_source": "Some wiki text"}
        job = {"id": "testpostimport", "source": "BGWiki", "title": "Medusa",
               "state": "queued", "log": [], "error": None}
        with patch.object(wiki_jobs, "_fetch", return_value=[item]), patch.object(
            wiki_jobs.wiki_document, "build_blocks", return_value=("123", "mediawiki", [])
        ), patch.object(wiki_jobs.wiki_document, "store_document"), patch.object(
            wiki_jobs.wiki_document, "ensure_title_alias"
        ):
            wiki_jobs._run(job, str(db))
        assert job["state"] == "done", job
        assert job["verified_pages"] == 1, job
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT title FROM reference_wiki_pages").fetchone() == ("Medusa",)
    print("Wiki post-import verification: PASS")


if __name__ == "__main__":
    main()
