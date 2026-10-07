from __future__ import annotations

import gzip
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from workbench.devtools.reference import build_wiki_index as canonical
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT


def main() -> None:
    assert not (Path(__file__).resolve().parents[1] / "build_wiki_index.py").exists()

    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.DUMP_PATH == VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"
    assert canonical.normalize("Jaggedy-Eared Jack") == "jaggedyearedjack"
    assert canonical.is_excluded({"categories": ["CatsEyeXI"]})
    assert not canonical.is_excluded({"categories": ["Notorious Monsters"]})

    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "wiki.jsonl.gz"
        pages = [
            {
                "title": "Page One",
                "url": "https://example.invalid/one",
                "categories": [],
                "wikitext": "[[Leujaoam Sanctum]] {{Item Tooltip|Siren's Tear}}",
            },
            {
                "title": "Private Page",
                "url": "https://example.invalid/private",
                "categories": ["CatsEyeXI"],
                "wikitext": "[[Should Not Index]]",
            },
        ]
        with gzip.open(dump, "wt", encoding="utf-8") as handle:
            for page in pages:
                handle.write(json.dumps(page) + "\n")

        con = sqlite3.connect(":memory:")
        with patch.object(canonical, "DUMP_PATH", dump):
            total = canonical.build_index(con, progress_every=100)
        assert total == 2
        assert con.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0] == 1
        refs = con.execute("SELECT norm_name FROM wiki_entity_refs ORDER BY norm_name").fetchall()
        assert refs == [("leujaoamsanctum",), ("sirenstear",)]
        con.close()

    print("Wiki index package migration: PASS")


if __name__ == "__main__":
    main()
