"""Imported Medusa must take precedence over an older offline BG dump."""
import sqlite3, tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_evidence

def main():
    with tempfile.TemporaryDirectory() as directory:
        with sqlite3.connect(Path(directory)/"wiki.db") as con:
            wiki_evidence.init_db(con)
            con.execute("""INSERT INTO reference_wiki_pages
                (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
                VALUES (?,?,?,?,?,?,?,?)""",
                ("BGWiki","123","Medusa","medusa","2","","Latest cached article","abc"))
            with patch.object(wiki_evidence,"find_bg_page",return_value={
                "title":"Medusa","pageid":987,"wikitext":"Old offline dump"
            }) as fallback:
                by_title=wiki_evidence.find_reference_page(con,"BGWiki","Medusa")
                by_id=wiki_evidence.find_reference_page(con,"BGWiki","123")
                assert by_title["page_id"]=="123",by_title
                assert by_id["page_id"]=="123",by_id
                assert by_title["page_text"]=="Latest cached article"
                fallback.assert_not_called()
            jp=wiki_evidence.find_reference_page(con,"WikiWikiJP","Not present")
            assert jp is None
    print("Wiki Browse cached-first lookup: PASS")

if __name__=="__main__":
    main()
