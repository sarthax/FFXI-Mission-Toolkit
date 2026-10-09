"""BG Wiki MediaWiki revisions may return content inside main slots."""
from workbench.devtools.reference import scrape_bg_wiki as bg


def main():
    page={"title":"Medusa","pageid":123,"ns":0,"revisions":[
        {"revid":456,"timestamp":"2026-10-09T00:00:00Z","slots":{"main":{"content":"== Medusa =="}}}
    ]}
    row=bg._page_to_row(page)
    assert row["title"]=="Medusa"
    assert row["wikitext"]=="== Medusa =="
    page["revisions"][0]["content"]="Legacy text"
    assert bg._page_to_row(page)["wikitext"]=="Legacy text"
    del page["revisions"][0]["content"]
    del page["revisions"][0]["slots"]
    try:
        bg._page_to_row(page)
    except RuntimeError as exc:
        assert "revision content unavailable" in str(exc)
    else:
        raise AssertionError("Missing revision contents silently accepted")
    print("BG Wiki main slot regression: PASS")


if __name__ == "__main__":
    main()
