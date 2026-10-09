"""Guarded Wiki recovery applies only to a previewed, unchanged legacy-only page."""
import hashlib
import sqlite3
from workbench.devtools.reference import wiki_document
from workbench.devtools.reference.wiki_import_audit import (
    apply_local_recovery, preview_local_recovery,
)

def main():
    con=sqlite3.connect(":memory:")
    wiki_document.init_db(con)
    raw="== 戦利品 ==\n* [[Mars's Ring]]"
    source,page="WikiWikiJP","nm-legacy"
    con.execute("""INSERT INTO reference_wiki_documents
      (source_id,page_id,source_format,raw_source,raw_hash,parser_version)
      VALUES (?,?,?,?,?,?)""",(source,page,"mediawiki",raw,
                                 hashlib.sha256(raw.encode()).hexdigest(),wiki_document.PARSER_VERSION))
    con.execute("""INSERT INTO reference_wiki_blocks
      (source_id,page_id,block_id,ordinal,block_type,text)
      VALUES (?,?,?,?,?,?)""",(source,page,"old-block",1,"legacy_text",raw))
    con.commit()
    preview=preview_local_recovery(con)
    assert len(preview)==1 and preview[0]["source_hash"]==hashlib.sha256(raw.encode()).hexdigest()
    for expected_hash,confirm in ((preview[0]["source_hash"],False),("0"*64,True)):
        try:
            apply_local_recovery(con,source=source,page_id=page,
                                 expected_raw_hash=expected_hash,confirm=confirm)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected authorization/hash guard")
        assert con.execute("SELECT block_type FROM reference_wiki_blocks").fetchall()==[("legacy_text",)]
    result=apply_local_recovery(con,source=source,page_id=page,
                                expected_raw_hash=preview[0]["source_hash"],confirm=True)
    assert result["applied"] and result["validation"]=="PASSED"
    assert result["structure"]["blocks"]>1
    assert result["structure"]["types"].get("heading",0)>=1
    assert result["structure"]["with_source_locator"]>=1
    assert con.execute("SELECT count(*) FROM reference_wiki_blocks WHERE block_type='legacy_text'").fetchone()[0]==0
    assert con.execute("SELECT raw_source FROM reference_wiki_documents").fetchone()[0]==raw
    try:
        apply_local_recovery(con,source=source,page_id=page,
                             expected_raw_hash=preview[0]["source_hash"],confirm=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Repeated apply should reject already-structured blocks")
    print("Wiki guarded local recovery: PASS")

if __name__=="__main__":
    main()
