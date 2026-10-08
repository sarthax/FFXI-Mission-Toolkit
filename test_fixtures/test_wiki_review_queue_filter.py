from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    ui=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert 'review_status: str = "all"' in host
    assert 'entry[review_status]' in host
    assert '("pending", "dismissed")' in host
    assert "review_status={{ state }}" in ui
    print("Wiki queue status filters: PASS")

if __name__=="__main__":
    main()
