#!/usr/bin/env python3
"""Validate that every FastAPI GUI route has exactly one canonical IA home."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
GUI=ROOT/"gui_server.py"
ROUTE_MAP=ROOT/"docs"/"workbench"/"GUI_ROUTE_MAP.json"


def main():
    source=GUI.read_text(encoding="utf-8")
    registered=[
        (m.group(1).upper(),m.group(2))
        for m in re.finditer(
            r'^@app\.(get|post|put|delete|patch)\("([^"]+)"',
            source,
            flags=re.MULTILINE,
        )
    ]
    payload=json.loads(ROUTE_MAP.read_text(encoding="utf-8"))
    mapped=[(row["method"],row["path"]) for row in payload["routes"]]

    assert payload["route_count"]==len(registered),payload["route_count"]
    assert len(registered)>0,len(registered)
    assert len(mapped)==len(registered),len(mapped)
    assert len(set(mapped))==len(mapped),"duplicate method/path mapping"
    assert set(registered)==set(mapped),{
        "missing_from_map":sorted(set(registered)-set(mapped)),
        "stale_in_map":sorted(set(mapped)-set(registered)),
    }
    assert all(row.get("home") for row in payload["routes"]),"empty canonical home"
    assert all(row.get("section") for row in payload["routes"]),"empty section"
    assert all(row.get("disposition") in {"KEEP","REWORK","MERGE","LEGACY"} for row in payload["routes"])

    print("GUI information architecture route map self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
