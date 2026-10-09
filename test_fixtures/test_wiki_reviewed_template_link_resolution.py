"""Resolve explicit template links conservatively against reviewed topics."""
import sqlite3
from workbench.devtools.reference import wiki_document, wiki_evidence

def main():
    db=sqlite3.connect(":memory:")
    wiki_evidence.init_db(db)
    wiki_document.init_db(db)
    links=wiki_document.template_field_review_links("[[Mars's_Ring|Ring]] [[Unknown_Foo]]")
    before=wiki_document.resolve_reviewed_template_links(db,links)
    assert [x["resolution"] for x in before]==["UNRESOLVED","UNRESOLVED"],before
    wiki_document.link_topic(db,source_id="FFXIclopedia",page_id="ring1",
                             canonical_title="Mars's Ring",method="MANUAL_REVIEW")
    after=wiki_document.resolve_reviewed_template_links(db,links)
    assert after[0]["resolution"]=="UNIQUE_REVIEWED_TOPIC",after
    assert after[0]["topic_id"] and after[0]["review_only"]
    assert after[1]["resolution"]=="UNRESOLVED"
    assert after[1]["topic_id"] is None
    assert db.execute("SELECT count(*) FROM reference_wiki_topic_pages").fetchone()[0]==1
    print("Wiki reviewed link resolution: PASS")

if __name__=="__main__":
    main()
