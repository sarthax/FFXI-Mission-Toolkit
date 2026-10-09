"""Unified Wiki status must remain source-accurate and read-only to the network."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_sync_overview as overview

def main():
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        with patch.object(overview.wiki_bulk_jobs,"status",return_value=[
            {"id":"fx","state":"completed","processed":50}]),patch.object(
            overview.wiki_bg_dump_jobs,"status",return_value=[
            {"id":"bg","state":"interrupted","processed":13}]),patch.object(
            overview.wiki_jp_crawl_jobs,"status",return_value=[
            {"id":"jp","state":"paused","processed":4,"pending":2}]),patch.object(
            overview.wiki_sync_schedule,"settings",return_value={
            "enabled":1,"next_due":"2026-10-10T00:00:00+00:00"}),patch.object(
            overview.wiki_bulk_jobs,"sync_summary",return_value={"last_success":{"changed":{"runs":1}}}):
            result=overview.overview(db)
        assert [x["source"] for x in result["sources"]]==["FFXIclopedia","BGWiki","WikiWikiJP"]
        assert result["sources"][0]["schedule"]["enabled"]==1
        assert result["sources"][1]["schedule"] is None
        assert result["sources"][1]["attention"][0]["state"]=="interrupted"
        assert result["sources"][2]["attention"][0]["state"]=="paused"
        assert result["sources"][0]["needs_attention"] is False
        assert result["sources"][1]["needs_attention"] is True
        assert result["sources"][1]["recovery"][0]["checkpoint"]=="verify-archive"
        assert result["sources"][2]["recovery"][0]["checkpoint"]=="available"
        assert "scheduled" not in result["notice"].split("Japanese Wiki")[0]
    print("Wiki unified sync overview: PASS")
if __name__=="__main__": main()
