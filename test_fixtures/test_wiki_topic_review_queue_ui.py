"""Wiki review queue stays read-only and lists pending/dismissed separately."""
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    ui=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert 'wiki_document.topic_review_queue(' in host
    assert 'matching_only=True' in host
    assert '"review_queue": review_queue' in host
    assert '<b>Topic review queue</b>' in ui
    assert '{% for entry in review_queue %}' in ui
    assert 'entry.pending' in ui and 'entry.dismissed' in ui
    assert 'Read-only overview' in ui
    print("Wiki topic review queue UI regression: PASS")

if __name__=="__main__":
    main()
