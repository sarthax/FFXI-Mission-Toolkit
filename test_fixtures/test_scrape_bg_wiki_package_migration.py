from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from workbench.devtools.reference import scrape_bg_wiki as canonical
from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT


def main() -> None:
    assert not (REPO_ROOT / "scrape_bg_wiki.py").exists()
    assert canonical.DUMP_PATH == VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

    row = canonical._page_to_row({
        "title": "The Siren's Tear",
        "pageid": 123,
        "ns": 0,
        "categories": [{"title": "Category:Quest"}],
        "revisions": [{"revid": 456, "timestamp": "2026-10-02T00:00:00Z", "content": "body"}],
    })
    assert row is not None
    assert row["title"] == "The Siren's Tear"
    assert row["categories"] == ["Quest"]
    assert row["wikitext"] == "body"

    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "bg-wiki.jsonl.gz"
        rows = {row["title"]: row}
        with patch.object(canonical, "DUMP_PATH", dump):
            canonical.write_dump(rows)
            loaded = canonical.load_existing_dump()
        assert loaded == rows

    with patch.object(canonical, "load_existing_dump", return_value={"One": {"title": "One", "timestamp": "2026-01-01T00:00:00Z"}}), patch.object(
        canonical, "fetch_changed_titles_since", return_value=[]
    ):
        assert canonical.run_incremental(None) == (1, 0)

    print("BG Wiki scraper package migration: PASS")


if __name__ == "__main__":
    main()
