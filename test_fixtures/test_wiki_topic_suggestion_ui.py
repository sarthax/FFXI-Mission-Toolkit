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
    assert 'target="_blank" rel="noopener"' in template
    assert "do not link pages automatically" in template
    assert 'wiki_evidence.resolve_subject(con,link.get("lookup_title") or "")' in host
    assert 'link["entity_resolution"]="UNIQUE_ENTITY_HINT"' in host
    assert 'link["entity_resolution"]="AMBIGUOUS" if identities else "UNRESOLVED"' in host
    assert 'Toolkit entity: {{ link.entity_resolution }}' in template
    assert 'review hint only' in template
    print("Wiki multilingual suggestion reader regression: PASS")

if __name__=="__main__":
    main()
