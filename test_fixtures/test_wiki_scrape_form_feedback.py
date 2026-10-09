"""Scrape submission must never fail without visible feedback."""
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    template = (root / "gui/templates/wiki.html").read_text(encoding="utf-8")
    jobs = (root / "src/workbench/devtools/reference/wiki_jobs.py").read_text(encoding="utf-8")
    assert "fetch('/wiki/scrape',{method:'POST',body:new FormData(f)})" in template
    assert "Scrape request failed:" in template
    assert "Cannot check scrape progress:" in template
    assert "Scrape job queued:" in template
    assert "button.disabled=true" in template
    assert "node.textContent=" in template  # Never inject remote errors as HTML.
    assert "job[\"state\"] = \"error\"" in jobs
    assert 'if not fetched:' in jobs


if __name__ == "__main__":
    main()
