"""Wiki workspace tab groups keep existing form and route identities."""
from pathlib import Path


def main():
    html=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    for pane in ("scrape","batch","monitor","utilities"):
        assert 'id="wiki-pane-'+pane+'"' in html
        assert 'data-wiki-pane="'+pane+'"' in html
    for form in ("scrape-form","wiki-jp-bulk-form","wiki-bg-bulk-form",
                 "wiki-bulk-start","wiki-snapshot-import","wiki-diagnose-form"):
        assert 'id="'+form+'"' in html
    assert "pane.appendChild(section)" in html
    assert "section.open=true" in html
    assert "pane.hidden=key!==group" in html
    assert "select('scrape')" in html
    assert "fetch('/wiki/scrape',{method:'POST'" in html
    assert "wiki-workspace-pane>details.wiki-section>summary" in html
    print("Wiki workspace tabs: PASS")


if __name__=="__main__":
    main()
