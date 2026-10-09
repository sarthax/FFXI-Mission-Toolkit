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
    assert 'if tab == "recovery":' in host
    assert 'preview_local_recovery(con, sample_limit=12)' in host
    assert '"recovery_preview": recovery_preview' in host
    assert "tab=recovery" in ui
    assert "Local Wiki structure recovery — preview only" in ui
    assert "entry.block_type_deltas" in ui
    assert '@app.post("/wiki/recovery/apply")' in host
    assert 'apply_local_recovery(con,source=source,page_id=page_id,' in host
    assert 'confirmed = str(form.get("confirm") or "") == "yes"' in host
    assert 'recovery_result=failed' in host
    assert 'recovery_result=applied' in host
    assert 'method="post" action="/wiki/recovery/apply"' in ui
    assert 'name="source_hash" value="{{ entry.source_hash }}"' in ui
    assert 'name="confirm" value="yes" required' in ui
    print("Wiki topic review queue UI regression: PASS")

if __name__=="__main__":
    main()
