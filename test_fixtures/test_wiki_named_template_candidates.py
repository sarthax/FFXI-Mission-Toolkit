"""Named Wiki template fields yield provenance-preserving review hints only."""
from workbench.devtools.reference.wiki_document import presentation_groups

def main():
    blocks=[
        {"block_type":"template_field","text":"[[Mars's Ring]]",
         "source_locator":"section:Rewards:template:1:field:1",
         "metadata":{"template":"NM Info","field":"Drops","raw_value":"[[Mars's Ring]]"}},
        {"block_type":"template_field","text":"特定条件",
         "source_locator":"section:条件:template:1:field:2",
         "metadata":{"template":"NM","field":"必要条件","raw_value":"特定条件"}},
        {"block_type":"template_field","text":"Unverified prose",
         "source_locator":"section:Misc:template:1:field:3",
         "metadata":{"template":"NM","field":"Notes","raw_value":"Unverified prose"}},
    ]
    content=presentation_groups(blocks)[0]["content"]
    a=content[0]["field_candidate"]
    assert a["field_type"]=="DROPS" and a["review_only"]
    assert a["value_raw"]=="[[Mars's Ring]]"
    assert a["source_locator"]=="section:Rewards:template:1:field:1"
    assert content[1]["field_candidate"]["field_type"]=="REQUIRES"
    assert content[2]["field_candidate"] is None
    print("Wiki named-template candidate regression: PASS")

if __name__=="__main__":
    main()
