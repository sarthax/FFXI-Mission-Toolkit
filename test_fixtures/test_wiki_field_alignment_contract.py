"""Wiki field extraction contract across English/JP source formats.

Run: python test_fixtures/test_wiki_field_alignment_contract.py
Candidates remain presentation-only and must preserve original source locators.
"""
from workbench.devtools.reference.wiki_document import (
    mediawiki_blocks, presentation_groups, normalize_search,
)


def main():
    raw = """== Rewards ==
{{NM Info|Drops=[[Mars's Ring]]|Notes=Do not promote this prose}}
== 条件 ==
{{NM|必要条件=[[だいじなもの]]|備考=推測のみ}}
== Drops ==
{|
! Field !! Value
|-
| Drops || [[Mars's Ring]]
|-
| Notes || Rumored additional drop
|-
| 報酬 || [[報酬アイテム]]
|}
"""
    blocks = mediawiki_blocks("mixed-en-jp", raw)
    groups = presentation_groups(blocks)
    definitions = [item for group in groups for item in group["content"]
                   if item["type"] == "definition"]
    candidates = [item["field_candidate"] for item in definitions
                  if item.get("field_candidate")]
    assert candidates, "No template field candidates"
    by_field = {c["field"]: c for c in candidates}
    assert by_field["Drops"]["field_type"] == "DROPS"
    assert by_field["必要条件"]["field_type"] == "REQUIRES"
    assert all(c["review_only"] is True for c in candidates)
    assert all(c["source_locator"] for c in candidates)
    assert all(c["value_raw"] for c in candidates)
    assert not any(c["field"] in {"Notes", "備考"} for c in candidates)
    assert "[[だいじなもの]]" in by_field["必要条件"]["value_raw"]
    tables = [item for group in groups for item in group["content"]
              if item["type"] == "table"]
    assert len(tables) == 1
    table_candidates = tables[0]["field_candidates"]
    assert {c["field"] for c in table_candidates} == {"Drops", "報酬"}
    assert all(c["review_only"] is True for c in table_candidates)
    assert normalize_search("　報酬　") == "報酬"
    print("Wiki field alignment source-contract regression: PASS")


if __name__ == "__main__":
    main()
