"""In-memory samples verify read-only Wiki imported-block coverage accounting."""
import sqlite3
from workbench.devtools.reference.wiki_import_audit import audit, preview_local_recovery


def main():
    con=sqlite3.connect(":memory:")
    assert audit(con)["status"]=="NO_STRUCTURED_BLOCKS_TABLE"
    con.execute("CREATE TABLE reference_wiki_blocks (source_id TEXT,page_id TEXT,block_type TEXT,source_locator TEXT)")
    con.executemany("INSERT INTO reference_wiki_blocks VALUES (?,?,?,?)",[
      ("WikiWikiJP","jp-nm","template_field","section:戦利品:template:1:field:1"),
      ("WikiWikiJP","jp-nm","heading","section:戦利品"),
      ("WikiWikiJP","old","legacy_text",None),
      ("BG Wiki","en-item","template_field","section:drops:template:1:field:1"),
    ])
    report=audit(con,sample_limit=2)
    jp=next(s for s in report["sources"] if s["source"]=="WikiWikiJP")
    assert jp=={"source":"WikiWikiJP","pages_with_blocks":2,"blocks":3,"template_fields":1,"degraded_blocks":1},jp
    assert report["recovery_candidates"]==[{"source":"WikiWikiJP","page_id":"old","legacy_blocks":1,
                                            "recovery_action":"SELECTIVE_SOURCE_FETCH","source_format":None}]
    con.execute("CREATE TABLE reference_wiki_documents (source_id TEXT,page_id TEXT,source_format TEXT,raw_source TEXT)")
    con.execute("INSERT INTO reference_wiki_documents VALUES (?,?,?,?)",
                ("WikiWikiJP","old","mediawiki","== 戦利品 ==\\n* [[Item]]"))
    recovered=audit(con)
    assert recovered["recovery_candidates"][0]["recovery_action"]=="REPARSE_LOCAL_SOURCE"
    assert recovered["recovery_candidates"][0]["source_format"]=="mediawiki"
    preview=preview_local_recovery(con)
    assert len(preview)==1,preview
    assert preview[0]["page_id"]=="old"
    assert preview[0]["preview_block_count"]>0
    assert preview[0]["requires_confirmation"] is True and preview[0]["applied"] is False
    assert con.execute("SELECT COUNT(*) FROM reference_wiki_blocks").fetchone()[0]==4

    assert len(report["samples"])==2
    assert report["samples"][0]["template_fields"]==1
    assert report["samples"][0]["source_locators"]==1
    assert audit(con,sample_limit=0)["samples"]==[]
    assert audit(con,sample_limit=0)["recovery_candidates"]==[]
    assert con.execute("SELECT COUNT(*) FROM reference_wiki_blocks").fetchone()[0]==4
    print("Wiki imported coverage audit: PASS")


if __name__=="__main__":
    main()
