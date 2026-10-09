"""Unified Wiki status must remain source-accurate and read-only to the network."""
import tempfile
import json
import sqlite3
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
    # Verify real persisted queue metadata rather than a status-only hint.
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"checkpoints.db"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE wiki_bulk_jobs(id TEXT,pending_json TEXT)")
            con.execute("CREATE TABLE wiki_jp_crawl_jobs(id TEXT,queue_json TEXT)")
            con.execute("CREATE TABLE wiki_bg_dump_jobs(id TEXT,dump_path TEXT,dump_signature TEXT)")
            con.execute("INSERT INTO wiki_bulk_jobs VALUES (?,?)",
                        ("fx",json.dumps(["Medusa"])))
            con.execute("INSERT INTO wiki_jp_crawl_jobs VALUES (?,?)",
                        ("jp",json.dumps([])))
        assert overview._verified_checkpoint(db,"FFXIclopedia","fx")=="available"
        assert overview._verified_checkpoint(db,"WikiWikiJP","jp")=="empty-checkpoint"
        with sqlite3.connect(db) as con:
            con.execute("UPDATE wiki_bulk_jobs SET pending_json=? WHERE id='fx'",
                        ('{"bad":"shape"}',))
        assert overview._verified_checkpoint(db,"FFXIclopedia","fx")=="invalid-checkpoint"
        assert overview._verified_checkpoint(db,"BGWiki","missing")=="verify-archive"
        archive=Path(root)/"bg.jsonl.gz"
        archive.write_bytes(b"original")
        signature=f"{archive.stat().st_size}:{archive.stat().st_mtime_ns}"
        with sqlite3.connect(db) as con:
            con.execute("INSERT INTO wiki_bg_dump_jobs VALUES (?,?,?)",
                        ("bg",str(archive),signature))
        assert overview._verified_checkpoint(db,"BGWiki","bg")=="available"
        archive.write_bytes(b"different-content")
        assert overview._verified_checkpoint(db,"BGWiki","bg")=="archive-changed"
        archive.unlink()
        assert overview._verified_checkpoint(db,"BGWiki","bg")=="archive-missing"

    # The dashboard must route recovery warnings to source-specific controls
    # without silently issuing POST/resume requests.
    ui=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    for target in ("wiki-bulk-box","wiki-bg-bulk-box","wiki-jp-bulk-box"):
        assert target in ui
    assert "source.recovery||[]" in ui
    assert "Review '+source.source+' job controls" in ui
    assert "Verify the original local compressed archive" in ui
    assert "Checkpoint not verified here" in ui
    print("Wiki unified sync overview: PASS")
if __name__=="__main__": main()
