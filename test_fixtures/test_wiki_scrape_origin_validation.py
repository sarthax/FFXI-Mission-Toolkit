"""Offline tests for strict, source-aware Wiki scrape URL validation."""
from workbench.devtools.reference import wiki_jobs


def main():
    valid = {
        "https://www.bg-wiki.com/ffxi/Medusa": ("BGWiki", "Medusa"),
        "https://bg-wiki.com/ffxi/Medusa": ("BGWiki", "Medusa"),
        "https://ffxiclopedia.fandom.com/wiki/Medusa": ("FFXIclopedia", "Medusa"),
        "https://wikiwiki.jp/ffxi/Medusa": ("WikiWikiJP", "Medusa"),
    }
    for url, expected in valid.items():
        assert wiki_jobs.detect(url) == expected, url

    invalid = (
        "https://evilbg-wiki.com/ffxi/Medusa",
        "https://bg-wiki.com.evil.test/ffxi/Medusa",
        "https://notffxiclopedia.fandom.com/wiki/Medusa",
        "https://wikiwiki.jp.evil.test/ffxi/Medusa",
        "http://www.bg-wiki.com/ffxi/Medusa",
        "https://www.bg-wiki.com:8443/ffxi/Medusa",
        "https://user@www.bg-wiki.com/ffxi/Medusa",
        "https://www.bg-wiki.com/ffxi/../Medusa",
        "https://www.bg-wiki.com/ffxi/",
        "https://www.bg-wiki.com/ffxi/Medusa?redirect=1",
    )
    for url in invalid:
        assert wiki_jobs.detect(url) is None, url
    print("Wiki scrape origin validation: PASS")


if __name__ == "__main__":
    main()
