"""Wiki Compiler displays local cache health without changing cached content."""
from pathlib import Path


def main():
    html=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    assert 'id="wiki-cache-panel"' in html
    assert "fetch('/wiki/cache-health',{cache:'no-store'})" in html
    assert "wikiCacheMetric('Structured documents'" in html
    assert "wikiCacheMetric('Structured blocks'" in html
    assert "'BGWiki','FFXIclopedia','WikiWikiJP','BGWiki_dump_index'" in html
    assert 'cacheBtn.addEventListener(\'click\',updateWikiCache)' in html
    assert "cachePath.textContent='Database: '" in html
    assert "cacheKpis.replaceChildren()" in html
    print("Wiki inline cache coverage: PASS")


if __name__ == "__main__":
    main()
