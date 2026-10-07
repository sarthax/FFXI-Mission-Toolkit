#!/usr/bin/env python3
"""Regression coverage for Captain StatTrack CSV ingestion retained during branch reconciliation."""
from pathlib import Path

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.services import capture_integrity


PLAYER = """timestamp,hpmax,mpmax,mjob_no,mjob_lv,sjob_no,sjob_lv,STR,DEX,VIT,AGI,INT,MND,CHR
2026-09-28 12:00:00,1200,700,1,99,6,49,90,85,88,80,75,70,65
"""

PUPPET = """timestamp,maxhp,maxmp,maxmelee,maxranged,maxmagic,str,dex,vit,agi,int,mnd,chr
2026-09-28 12:00:01,1800,900,120,110,130,95,90,100,85,88,92,80
"""

assert build_capture_index.sniff_csv_format(PLAYER) == "stattrack_csv"
assert build_capture_index.sniff_csv_format(PUPPET) == "puppet_stattrack_csv"
assert "stattrack_csv" in build_capture_index.AUX_STRUCTURED_FORMATS
assert "puppet_stattrack_csv" in build_capture_index.AUX_STRUCTURED_FORMATS
assert capture_integrity.parser_targets("stattrack_csv") == (("capture_structured_records", "csv-row"),)
assert capture_integrity.parser_targets("puppet_stattrack_csv") == (("capture_structured_records", "csv-row"),)

help_text = Path("gui/templates/capture_help.html").read_text(encoding="utf-8")
assert "Captain StatTrack" in help_text
print("Captain StatTrack capture regression passed")
