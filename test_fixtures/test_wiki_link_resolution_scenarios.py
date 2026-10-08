"""Exercise structured Wiki NM/item/zone/JP link evidence end to end (offline fixture)."""
import sqlite3
from workbench.devtools.reference import wiki_document, wiki_evidence

def main():
    con=sqlite3.connect(":memory:")
    wiki_evidence.init_db(con)
    wiki_document.init_db(con)
    cases=[
        ("Drops","[[Mars's_Ring|Ring]]","DROPS","Mars's Ring"),
        ("Location","[[Al'Taieu]]","LOCATION","Al'Taieu"),
        ("NM Name","[[Absolute Virtue]]","NM_IDENTITY","Absolute Virtue"),
        ("ミッション","[[星唄の煌めき]]","QUEST","星唄の煌めき"),
    ]
    for field,markup,expected_kind,expected_title in cases:
        blocks=[{"block_type":"template_field","text":expected_title,
                 "source_locator":"section:test:template:1:field:1",
                 "metadata":{"template":"Test","field":field,"raw_value":markup}}]
        candidate=wiki_document.presentation_groups(blocks)[0]["content"][0]["field_candidate"]
        assert candidate["field_type"]==expected_kind,(field,candidate)
        assert candidate["source_locator"]=="section:test:template:1:field:1"
        assert candidate["source_links"][0]["lookup_title"]==expected_title
        before=wiki_document.resolve_reviewed_template_links(con,candidate["source_links"])
        assert before[0]["resolution"]=="UNRESOLVED",before
        wiki_document.link_topic(con,source_id="FFXIclopedia",page_id="test:"+field,
                                 canonical_title=expected_title,method="MANUAL_REVIEW")
        after=wiki_document.resolve_reviewed_template_links(con,candidate["source_links"])
        assert after[0]["resolution"]=="UNIQUE_REVIEWED_TOPIC",after
        assert after[0]["review_only"]
    assert con.execute("SELECT count(*) FROM reference_wiki_topic_pages").fetchone()[0]==len(cases)
    print("Wiki link resolution scenarios: PASS")

if __name__=="__main__":
    main()
