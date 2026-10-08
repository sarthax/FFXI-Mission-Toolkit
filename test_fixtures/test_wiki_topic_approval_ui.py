"""Wiki topic suggestion approval remains explicit and server validated."""
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    template=(root/"gui/templates/wiki.html").read_text(encoding="utf-8")
    host=(root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    for fragment in ('name="suggested_topic_id"', 'value="{{ suggestion.topic_id }}"',
                     'Approve and link topic'):
        assert fragment in template,fragment
    assert 'if suggested_topic_id:' in host
    assert 'item["topic_id"] == suggested_topic_id and item["canonical_title"] == canonical_title' in host
    assert 'Suggested topic no longer matches reviewed aliases' in host
    assert template.count('name="review_page" value="{{ review_page }}"') >= 2
    assert template.count('name="review_status" value="{{ review_status }}"') >= 2
    assert host.count('review_page_raw = (form.get("review_page") or "").strip()') >= 2
    assert host.count('tab=review&review_status={review_status}&review_page={review_page}') >= 2
    print("Wiki V2 reviewed topic approval UI regression: PASS")

if __name__=="__main__":
    main()
