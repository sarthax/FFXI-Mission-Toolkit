"""Wiki scrape diagnostics remain specific and do not hide failures."""
import sqlite3
import urllib.error
from workbench.devtools.reference import wiki_jobs


def main():
    cases = [
        (urllib.error.HTTPError("https://www.bg-wiki.com/ffxi/Medusa", 429, "limited", None, None), "fetching", "source_access"),
        (urllib.error.URLError("offline"), "fetching", "network"),
        (sqlite3.OperationalError("database is locked"), "merging", "cache_database"),
        (ValueError("parse failure"), "fetching", "source_import"),
        (ValueError("structure failure"), "merging", "cache_import"),
    ]
    for exc, phase, code in cases:
        found, advice = wiki_jobs._failure_guidance(exc, phase)
        assert found == code
        assert advice
    print("Wiki scrape diagnostics: PASS")


if __name__ == "__main__":
    main()
