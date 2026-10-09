"""Wiki table review candidates retain original evidence cell provenance."""
from workbench.devtools.reference import wiki_document


def main():
    raw="""== Rewards ==
{|
! Field !! Value
|-
| Drops || [[Mars's Ring]]
|}
"""
    blocks=wiki_document.mediawiki_blocks("p",raw)
    tables=[c for section in wiki_document.presentation_groups(blocks)
            for c in section["content"] if c["type"]=="table"]
    assert len(tables)==1
    c=tables[0]["field_candidates"][0]
    assert c["field"]=="Drops" and c["value"]=="Mars's Ring",c
    assert c["value_raw"]=="[[Mars's Ring]]",c
    assert c["value_source_locator"] is not None,c
    assert c["field_source_locator"] is not None,c
    assert c["review_only"] is True
    print("Wiki V2 candidate provenance regression: PASS")


if __name__=="__main__":
    main()
