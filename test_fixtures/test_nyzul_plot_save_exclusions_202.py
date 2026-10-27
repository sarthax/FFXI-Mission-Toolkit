"""#202: the Nyzul exclusion save wrapper must POST, never recurse into itself."""
import re
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[1] / "gui" / "templates" / "nyzul_plot.html").read_text(encoding="utf-8")


def _save_exclusions_body() -> str:
    match = re.search(r"async function saveExclusions\([^)]*\)\{(.*?)\}\s*\n", TEXT)
    assert match, "saveExclusions helper is missing"
    return match.group(1)


def test_save_exclusions_does_not_call_itself():
    assert "saveExclusions(" not in _save_exclusions_body()


def test_save_exclusions_posts_current_rules_and_returns_response():
    body = _save_exclusions_body()
    assert "fetch('/nyzul/exclusions'" in body
    assert "method:'POST'" in body
    assert "JSON.stringify(EXC)" in body
    assert "!r.ok" in body
    assert "return r" in body
