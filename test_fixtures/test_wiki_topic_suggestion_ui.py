"""Wiki topic suggestions remain explicitly review-only in the reader."""
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    template=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'wiki_document.suggest_topic_links(con, source_id=source, page_id=page_id)' in host
    assert '{% if not page_view.topic and page_view.topic_suggestions %}' in template
    assert '{{ suggestion.canonical_title }}' in template
    assert '{{ proof.source_id }} / {{ proof.page_id }}' in template
    assert "do not link pages automatically" in template
    print("Wiki multilingual suggestion reader regression: PASS")

if __name__=="__main__":
    main()
