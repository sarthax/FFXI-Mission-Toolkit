"""Snapshot download/import controls are wired to guarded backend routes."""
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    ui=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert '@app.get("/wiki/snapshot/export")' in host
    assert '@app.post("/wiki/snapshot/import")' in host
    assert "wiki_snapshot.export_snapshot(DB_PATH" in host
    assert "wiki_snapshot.import_snapshot(DB_PATH" in host
    assert "64 * 1024 * 1024" in host
    assert 'id="wiki-snapshot-box"' in ui
    assert 'action="/wiki/snapshot/export"' in ui
    assert "fetch('/wiki/snapshot/import'" in ui
    assert "new FormData(form)" in ui
    print("Wiki snapshot GUI routes: PASS")

if __name__=="__main__":main()
