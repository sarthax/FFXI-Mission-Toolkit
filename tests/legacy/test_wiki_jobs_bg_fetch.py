"""BG Wiki scrape must work in a fresh interpreter (no pre-imported wiki_evidence adapter)."""
import subprocess, sys, pathlib

SRC = str(pathlib.Path(__file__).resolve().parents[2] / "src")
CODE = r'''
import sys
sys.path.insert(0, %r)
from workbench.devtools.reference import wiki_jobs, scrape_bg_wiki
scrape_bg_wiki.fetch_pages_by_title = lambda titles: [dict(
    pageid=1, title="Lord Asag", revid=2, timestamp="t", wikitext="x")]
rows = wiki_jobs._fetch("BGWiki", "Lord_Asag", lambda m: None)
assert rows and rows[0]["row"][2] == "Lord Asag", rows
print("ok")
''' % SRC

r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True)
assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-800:]
print("ok: bg fetch in fresh interpreter")
