"""Link safety for Wiki V2 structured relation extraction."""
from workbench.devtools.reference import wiki_evidence as evidence


def main():
    valid = [
        ("WikiWikiJP", "/ffxi/マーズリング", "マーズリング"),
        ("FFXIclopedia", "Mars's_Ring#Drops", "Mars's Ring"),
    ]
    for source, target, expected in valid:
        assert evidence._internal_link_target(source, target) == expected
    invalid = ["javascript:alert(1)", "mailto:admin@example.com",
               "https://evil.example/item", "//evil.example/item",
               "#local", "?action=edit", "data:text/html,hi"]
    for target in invalid:
        assert evidence._internal_link_target("FFXIclopedia", target) is None, target
    print("Wiki V2 link target safety regression: PASS")


if __name__ == "__main__":
    main()
