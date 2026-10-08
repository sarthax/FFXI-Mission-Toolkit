"""Explicit Wiki table labels produce review-only presentation candidates."""
from workbench.devtools.reference import wiki_document

def main():
    raw="""== Information ==
{|
! Field !! Value
|-
| Drops || [[Mars's Ring]]
|-
| Notes || Must not imply drops
|-
| 報酬 || Reward item
|}
"""
    groups=wiki_document.presentation_groups(wiki_document.mediawiki_blocks("p",raw))
    tables=[x for g in groups for x in g["content"] if x["type"]=="table"]
    assert len(tables)==1,tables
    candidates=tables[0]["field_candidates"]
    assert [(c["field"],c["value"]) for c in candidates]==[
        ("Drops","Mars's Ring"),("報酬","Reward item")
    ],candidates
    assert all(c["review_only"] for c in candidates)
    print("Wiki V2 table candidates regression: PASS")

if __name__=="__main__":
    main()
