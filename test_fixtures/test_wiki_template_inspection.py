"""Wiki V2: named template fields stay review-only, with original values preserved."""
from workbench.devtools.reference import wiki_document


def main():
    text = """== Rewards ==
{{RewardTable|Item=[[Mars's Ring]]|Count=2|[[Ignored positional]]}}
"""
    blocks = wiki_document.mediawiki_blocks("fixture", text)
    fields = [b for b in blocks if b["block_type"] == "template_field"]
    assert [(b["metadata"]["field"],b["text"]) for b in fields] == [
        ("Item","Mars's Ring"),("Count","2")
    ], fields
    assert fields[0]["metadata"]["raw_value"] == "[[Mars's Ring]]"
    assert fields[0]["metadata"]["review_only"] is True
    assert fields[0]["section_path"] == "Rewards"
    groups = wiki_document.presentation_groups(blocks)
    assert any(c["type"]=="definition" and c["term"]=="RewardTable: Item"
               for group in groups for c in group["content"])
    print("Wiki V2 template inspection regression: PASS")


if __name__ == "__main__":
    main()
