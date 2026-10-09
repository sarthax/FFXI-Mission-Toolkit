"""Regression: Wiki scrape control must initialize without a JS syntax error."""
from pathlib import Path


def main():
    html = (Path(__file__).resolve().parents[1] / "gui/templates/wiki.html").read_text(encoding="utf-8")
    assert r"o.textContent='[machine translation, unverified]\n'+d.text;" in html
    assert "fetch('/wiki/scrape',{method:'POST',body:new FormData(f)})" in html
    assert "e.preventDefault();" in html
    assert "if(f){f.addEventListener('submit',function(e){" in html
    print("Wiki scrape JavaScript regression: PASS")


if __name__ == "__main__":
    main()
