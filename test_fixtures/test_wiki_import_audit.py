"""In-memory samples verify read-only Wiki imported-block coverage accounting."""
import sqlite3
from workbench.devtools.reference.wiki_import_audit import audit


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
    assert report["recovery_candidates"]==[{"source":"WikiWikiJP","page_id":"old","legacy_blocks":1}]
    assert len(report["samples"])==2
    assert report["samples"][0]["template_fields"]==1
    assert report["samples"][0]["source_locators"]==1
    assert audit(con,sample_limit=0)["samples"]==[]
    assert audit(con,sample_limit=0)["recovery_candidates"]==[]
    assert con.execute("SELECT COUNT(*) FROM reference_wiki_blocks").fetchone()[0]==4
    print("Wiki imported coverage audit: PASS")


if __name__=="__main__":
    main()
