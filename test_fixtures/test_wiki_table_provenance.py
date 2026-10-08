"""Wiki table provenance regression: raw content remains review-only."""
from workbench.devtools.reference import wiki_document

def main():
    raw="""== Rewards ==
{| class="wikitable"
! Item !! Quantity
|-
| [[Mars's Ring]] || 2
|}
"""
    blocks=wiki_document.mediawiki_blocks("page",raw)
    cells=[b for b in blocks if b["block_type"] in {"table_cell","table_header_cell"}]
    assert len(cells)==4,cells
    assert [b["text"] for b in cells]==["Item","Quantity","Mars's Ring","2"],cells
    assert cells[2]["metadata"]["raw_value"]=="[[Mars's Ring]]"
    assert all(b["metadata"]["review_only"] for b in cells)
    assert all(b["section_path"]=="Rewards" for b in cells)
    print("Wiki V2 table provenance regression: PASS")

if __name__=="__main__":
    main()
