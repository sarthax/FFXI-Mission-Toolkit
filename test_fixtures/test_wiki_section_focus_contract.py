"""Contract: Wiki section focus must not silently choose the first repeated heading.

Source-locator-based navigation requires exact disambiguation for duplicate headings.
This static regression guards the browser-side fail-closed behavior until a full
headless-browser acceptance run can be performed on the local installation.
"""
from pathlib import Path


def main():
    template=(Path(__file__).parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert "matches.length !== 1" in template
    assert "matches.length > 1" in template
    assert "const section = matches[0]" in template
    assert "The cited section heading is ambiguous" in template
    assert ".find(element => element.dataset.wikiSection === wanted)" not in template
    print("Wiki ambiguous section focus fail-closed contract: PASS")


if __name__=="__main__":
    main()
