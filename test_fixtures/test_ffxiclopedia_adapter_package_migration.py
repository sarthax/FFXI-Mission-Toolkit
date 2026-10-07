#!/usr/bin/env python3
"""Focused migration smoke for the FFXIclopedia reference adapter."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from workbench.devtools.reference import ffxiclopedia

    assert not (REPO_ROOT / "ffxiclopedia_adapter.py").exists()
    assert ffxiclopedia.norm_title("Cait Sith (Mission)") == "caitsithmission"

    code = r'''
from pathlib import Path
import sqlite3, tempfile
from workbench.devtools.reference import ffxiclopedia

xml = "<mediawiki xmlns='http://www.mediawiki.org/xml/export-0.11/'><page><title>Cait Sith (Mission)</title><id>42</id><revision><id>7</id><timestamp>2026-01-01T00:00:00Z</timestamp><text>Sample body</text></revision></page></mediawiki>"
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    source = root / "wiki.xml"
    db = root / "ref.db"
    source.write_text(xml, encoding="utf-8")
    result = ffxiclopedia.import_xml(source, db)
    assert result["pages"] == 1
    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT source_id,title,norm_title FROM reference_wiki_pages").fetchone()
        assert row == ("FFXIclopedia", "Cait Sith (Mission)", "caitsithmission")
    finally:
        con.close()
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        xml = root / "wiki.xml"
        db = root / "ref.db"
        xml.write_text("<mediawiki xmlns='http://www.mediawiki.org/xml/export-0.11/'></mediawiki>", encoding="utf-8")
        subprocess.run(
            [sys.executable, "-m", "workbench.devtools.reference.ffxiclopedia", str(xml), "--db", str(db)],
            cwd=td,
            check=True,
        )

    print("FFXIclopedia adapter package migration: PASS")


if __name__ == "__main__":
    main()
