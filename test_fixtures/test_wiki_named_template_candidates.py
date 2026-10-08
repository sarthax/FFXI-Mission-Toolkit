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
        {"block_type":"template_field","text":"Trade the rare item",
         "source_locator":"section:NM:template:1:field:4",
         "metadata":{"template":"NM","field":"Spawn Conditions","raw_value":"Trade the rare item"}},
        {"block_type":"template_field","text":"星唄の煌めき",
         "source_locator":"section:JP:template:1:field:5",
         "metadata":{"template":"Mission","field":"ミッション","raw_value":"星唄の煌めき"}},
        {"block_type":"template_field","text":"Absolute Virtue",
         "source_locator":"section:NM:template:1:field:6",
         "metadata":{"template":"NM","field":"NM Name","raw_value":"Absolute Virtue"}},
    ]
    content=presentation_groups(blocks)[0]["content"]
    a=content[0]["field_candidate"]
    assert a["field_type"]=="DROPS" and a["review_only"]
    assert a["source_links"]==[{"target":"Mars's Ring","source_markup":"[[Mars's Ring]]","review_only":True}]
    assert a["value_raw"]=="[[Mars's Ring]]"
    assert a["source_locator"]=="section:Rewards:template:1:field:1"
    assert content[1]["field_candidate"]["field_type"]=="REQUIRES"
    assert content[2]["field_candidate"] is None
    assert content[3]["field_candidate"]["field_type"]=="SPAWN_CONDITIONS"
    assert content[4]["field_candidate"]["field_type"]=="QUEST"
    assert content[5]["field_candidate"]["field_type"]=="NM_IDENTITY"
    assert all(x["field_candidate"]["review_only"] for x in content if x["field_candidate"])
    print("Wiki named-template candidate regression: PASS")

if __name__=="__main__":
    main()
