#!/usr/bin/env python3
"""Validate that every FastAPI GUI route has exactly one canonical IA home."""
from __future__ import annotations

import json
import re
from pathlib import Path

from workbench.gui_shell import WORKSPACES, build_shell_context


ROOT=Path(__file__).resolve().parents[1]
GUI=ROOT/"src"/"workbench"/"app"/"_host_impl.py"
ROUTE_MAP=ROOT/"docs"/"workbench"/"GUI_ROUTE_MAP.json"
AUX_ROUTE_MAP=ROOT/"docs"/"workbench"/"GUI_ROUTE_MAP_AUXILIARY.json"
TEMPLATES=ROOT/"gui"/"templates"


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
    auxiliary=json.loads(AUX_ROUTE_MAP.read_text(encoding="utf-8"))
    rows=[*payload["routes"],*auxiliary["routes"]]
    mapped=[(row["method"],row["path"]) for row in rows]
    missing=sorted(set(registered)-set(mapped))
    stale=sorted(set(mapped)-set(registered))

    assert not missing and not stale,{"missing_from_map":missing,"stale_in_map":stale}
    documented_count=payload["route_count"]+auxiliary["route_count"]
    assert documented_count==len(registered),{"documented":documented_count,"registered":len(registered)}
    assert len(registered)>0,len(registered)
    assert len(mapped)==len(registered),len(mapped)
    assert len(set(mapped))==len(mapped),"duplicate method/path mapping"
    assert all(row.get("home") for row in rows),"empty canonical home"
    assert all(row.get("section") for row in rows),"empty section"
    assert all(row.get("disposition") in {"KEEP","REWORK","MERGE","LEGACY"} for row in rows)

    # Features must remain generic; Assault mission coverage belongs to the Assault domain.
    features=next(workspace for workspace in WORKSPACES if workspace["name"]=="Features")
    assert features["href"]=="/features/trace",features
    assert {section["label"] for section in features["sections"]}=={
        "Feature Trace","Behavior Inspector","Feature Checker",
    },features["sections"]

    domains=next(workspace for workspace in WORKSPACES if workspace["name"]=="Domains")
    assert domains["href"]=="/domains",domains
    battle_systems=next(section for section in domains["sections"] if section["label"]=="Battle Systems")
    assault_missions=next(child for child in battle_systems["children"] if child["label"]=="Assault Missions")
    assert assault_missions["href"]=="/missions?q=__coverage_not_loaded__",assault_missions

    mission_shell=build_shell_context(
        path="/missions",method="GET",settings={},
        default_topaz_root="C:/missing-topaz",default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )
    assert mission_shell["active_home"]=="Domains",mission_shell["active_home"]
    assert mission_shell["active_section"]=="Battle Systems > Assault Missions",mission_shell["active_section"]

    assault_template=(TEMPLATES/"domain_assault.html").read_text(encoding="utf-8")
    missions_template=(TEMPLATES/"missions.html").read_text(encoding="utf-8")
    assert "/missions?q=__coverage_not_loaded__" in assault_template
    assert "Load all coverage" in assault_template
    assert "Load all observed coverage" in missions_template
    assert "Observed coverage is not loaded" in missions_template
    assert "q == '__coverage_not_loaded__'" in missions_template

    print("GUI information architecture route map self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
