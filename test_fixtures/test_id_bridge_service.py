#!/usr/bin/env python3
"""Focused regression for canonical ID Bridge service behavior."""
from __future__ import annotations

import io
import sqlite3
from contextlib import redirect_stdout
from pathlib import Path

from workbench.core.services import id_bridge
from workbench.runtime.paths import DATABASE_PATH


def main() -> None:
    assert not (Path(__file__).resolve().parents[1] / "id_bridge.py").exists()
    assert id_bridge.DB_PATH == DATABASE_PATH
    assert id_bridge.normalize("Chocobo Bedding") == "chocobobedding"

    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE items_external (id INTEGER, name TEXT, norm_name TEXT);
        CREATE TABLE items_ours (itemid INTEGER, name TEXT, norm_name TEXT);
        CREATE TABLE keyitems_external (id INTEGER, name TEXT, norm_name TEXT);
        CREATE TABLE keyitems_ours (id INTEGER, const_name TEXT, norm_name TEXT);
        """
    )
    con.execute(
        "INSERT INTO items_external VALUES (814, 'Chocobo Bedding', 'chocobobedding')"
    )
    con.execute(
        "INSERT INTO items_ours VALUES (500, 'chocobo_bedding', 'chocobobedding')"
    )

    output = io.StringIO()
    with redirect_stdout(output):
        id_bridge.lookup(con, "item", query="Chocobo Bedding")
    text = output.getvalue()
    assert "Topaz match by NAME" in text, text
    assert "external id 814 -> Topaz id 500" in text, text
    con.close()
    print("id bridge service self-test: PASS")


if __name__ == "__main__":
    main()
