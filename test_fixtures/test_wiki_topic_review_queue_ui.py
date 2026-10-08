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
    assert 'Back to topic review queue' in ui
    assert 'review_origin=1' in ui
    assert "{% if review_origin %}" in ui
    assert 'review_origin: bool = False' in host
    assert '"review_origin": review_origin' in host
    assert 'review_status={{ review_status }}&review_page={{ review_page }}' in ui
    assert 'entry.pending' in ui and 'entry.dismissed' in ui
    assert '{{ entry.pending|length }} pending' in ui
    assert '{{ entry.dismissed|length }} dismissed' in ui
    assert '{% for proof in item.supporting_pages %}' in ui
    assert 'proof.title|urlencode' in ui
    assert 'target="_blank" rel="noopener"' in ui
    assert 'Read-only overview' in ui
    print("Wiki topic review queue UI regression: PASS")

if __name__=="__main__":
    main()
