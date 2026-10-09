"""Read-only Wiki cache diagnostics do not create or migrate a database."""
from pathlib import Path
import sqlite3
import tempfile

from workbench.devtools.reference.wiki_jobs import cache_health


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.db"
        missing = cache_health(path)
        assert missing["database_exists"] is False
        assert not path.exists()
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE reference_wiki_pages (source_id TEXT, page_id TEXT)")
        con.executemany("INSERT INTO reference_wiki_pages VALUES (?, ?)", [
            ("BGWiki", "one"), ("WikiWikiJP", "jp1"), ("WikiWikiJP", "jp2")])
        con.commit()
        con.close()
        result = cache_health(path)
        assert result["database_exists"] is True
        assert result["sources"] == {"BGWiki": 1, "WikiWikiJP": 2}
        assert result["structured_documents"] is None
        assert result["structured_blocks"] is None
        con = sqlite3.connect(path)
        assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0] == 3
        con.close()
    print("Wiki cache health diagnostics: PASS")


if __name__ == "__main__":
    main()
