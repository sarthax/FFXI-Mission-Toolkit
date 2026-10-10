"""Guard Wiki scrape submit handler against unrelated dashboard JS exceptions."""
from pathlib import Path
import re

def main():
    source=(Path(__file__).resolve().parents[1]/"gui/templates/wiki.html").read_text(encoding="utf-8")
    scripts=re.findall(r"<script\b[^>]*>([\s\S]*?)</script>",source,flags=re.I)
    assert len(scripts)>=2
    handler=[script for script in scripts if "fetch('/wiki/scrape'" in script]
    assert len(handler)==1
    assert "var f=document.getElementById('scrape-form')" in handler[0]
    assert "e.preventDefault();" in handler[0]
    assert "fetch('/wiki/jobs'" in handler[0]
    assert "wiki-cache-panel" not in handler[0]
    assert '<form id="scrape-form" method="post" action="/wiki/scrape"' in source
    print("Wiki isolated scrape handler: PASS")

if __name__=="__main__":
    main()
