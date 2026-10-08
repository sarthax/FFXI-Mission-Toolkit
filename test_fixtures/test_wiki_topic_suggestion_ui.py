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
    assert '"DROPS":{"item","key_item"}' in host
    assert '"LOCATION":{"zone"}' in host
    assert '"NM_IDENTITY":{"entity"}' in host
    assert 'matches=[m for m in matches if m.get("target_domain") in allowed_domains]' in host
    assert 'else "NOT_APPLICABLE"' in host
    assert 'Toolkit entity: {{ link.entity_resolution }}' in template
    assert 'review hint only' in template
    assert 'link["entity_candidates"]=[' in host
    assert 'link["entity_candidate_count"]=len(identities)' in host
    assert '[:10]' in host
    assert 'Inspect entity candidates ({{ link.entity_candidate_count }})' in template
    assert '{{ link.entity_candidate_lines }}' in template
    assert 'href="/features/trace?q={{ link.entity_target.trace_query|urlencode }}"' in template
    assert 'search is not a verified mapping' in template
    assert '{% if link.entity_target %}' in template
    assert '"trace_query":("entity:"+key if domain=="entity" else key)' in host
    print("Wiki multilingual suggestion reader regression: PASS")

if __name__=="__main__":
    main()
