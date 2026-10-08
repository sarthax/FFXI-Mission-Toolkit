"""Exact reviewed alias topic suggestions cannot alter topic identity."""
import sqlite3
from workbench.devtools.reference import wiki_document, wiki_evidence


def main():
    db=sqlite3.connect(":memory:")
    wiki_evidence.init_db(db)
    wiki_document.init_db(db)
    for source,page,title in [
        ("WikiWikiJP","jp1","マーズリング"),
        ("FFXIclopedia","en1","Mars's Ring"),
        ("FFXIclopedia","en2","Unrelated")
    ]:
        db.execute("""INSERT INTO reference_wiki_pages
        (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
        VALUES (?,?,?,?,?,?,?,?)""",(source,page,title,wiki_document.normalize_search(title),None,None,"",""))
    wiki_document.link_topic(db,source_id="FFXIclopedia",page_id="en1",
        canonical_title="Mars's Ring",method="MANUAL_REVIEW")
    wiki_document.add_alias(db,source_id="FFXIclopedia",page_id="en1",
        alias="マーズリング",language="ja",alias_type="MANUAL",provenance="MANUAL_REVIEW")
    suggestions=wiki_document.suggest_topic_links(db,source_id="WikiWikiJP",page_id="jp1")
    assert len(suggestions)==1,suggestions
    assert suggestions[0]["canonical_title"]=="Mars's Ring",suggestions
    assert suggestions[0]["review_only"] is True
    assert wiki_document.page_topic(db,"WikiWikiJP","jp1") is None
    assert wiki_document.topic_review_queue(db,source_id="WikiWikiJP",limit=1,offset=1)==[]
    assert wiki_document.topic_review_queue(db,source_id="WikiWikiJP",matching_only=True)
    assert len(wiki_document.topic_review_queue(db,source_id="WikiWikiJP",matching_only=True,status="pending"))==1
    assert wiki_document.topic_review_queue(db,source_id="WikiWikiJP",matching_only=True,status="dismissed")==[]
    queue=wiki_document.topic_review_queue(db,source_id="WikiWikiJP")
    assert len(queue)==1 and len(queue[0]["pending"])==1 and queue[0]["dismissed"]==[],queue
    wiki_document.dismiss_topic_suggestion(db,source_id="WikiWikiJP",page_id="jp1",
                                           topic_id=suggestions[0]["topic_id"])
    assert wiki_document.suggest_topic_links(db,source_id="WikiWikiJP",page_id="jp1")==[]
    assert wiki_document.topic_review_queue(db,source_id="WikiWikiJP",matching_only=True,status="pending")==[]
    assert len(wiki_document.topic_review_queue(db,source_id="WikiWikiJP",matching_only=True,status="dismissed"))==1
    queue=wiki_document.topic_review_queue(db,source_id="WikiWikiJP")
    assert len(queue)==1 and queue[0]["pending"]==[] and len(queue[0]["dismissed"])==1,queue
    try:
        wiki_document.dismiss_topic_suggestion(db,source_id="WikiWikiJP",page_id="jp1",
                                               topic_id=suggestions[0]["topic_id"])
    except ValueError:
        pass
    else:
        raise AssertionError("Dismissal must reject stale suggestion")
    assert wiki_document.page_topic(db,"WikiWikiJP","jp1") is None
    assert wiki_document.suggest_topic_links(db,source_id="FFXIclopedia",page_id="en1")==[]
    assert wiki_document.suggest_topic_links(db,source_id="FFXIclopedia",page_id="en2")==[]
    print("Wiki V2 reviewed topic suggestion regression: PASS")


if __name__=="__main__":
    main()
