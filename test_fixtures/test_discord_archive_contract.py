"""Source contract tests for recovered Discord archive; local SQLite/browser acceptance pending."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "src/workbench/app/_host_impl.py"


def handler(name):
    tree = ast.parse(HOST.read_text(encoding="utf-8"))
    matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == name]
    assert len(matches) == 1, name
    return ast.get_source_segment(HOST.read_text(encoding="utf-8"), matches[0])


def test_discord_archive_routes_and_form_guard():
    source = HOST.read_text(encoding="utf-8")
    assert '@app.get("/captures/discord"' in source
    assert '@app.post("/captures/discord/link")' in source
    assert '@app.get("/captures/discord/export.{fmt}")' in source
    assert source.index('@app.get("/captures/discord"') < source.index('@app.get("/captures/{capture_id}"')
    link = handler("capture_discord_link")
    assert '_require_discord_local_origin(request)' in link
    assert 'cid_txt.isdecimal()' in link
    assert 'if st == "ingested" and cid is None:' in link
    assert 'UPDATE discord_posts SET capture_id=?, ingest_status=? WHERE message_id=?' in link
    assert 'safe_back' in link
    guard = handler("_require_discord_local_origin")
    assert 'same-origin request required' in guard
    assert 'Discord archive writes require a local browser' in guard


def test_discord_missing_cache_does_not_make_schema_changes():
    page = handler("capture_discord_archive")
    assert 'sqlite_master' in page
    assert 'Discord archive not indexed yet' in page
    assert 'CREATE TABLE' not in page and 'DROP TABLE' not in page
    assert 'discord["safe_links"]' in HOST.read_text(encoding="utf-8")
    assert 'startswith(("https://", "http://"))' in page
    assert 'w.writerow(' in handler("capture_discord_export")


def test_discord_templates_do_not_render_raw_link_schemes():
    archive = (ROOT / "gui/templates/capture_discord.html").read_text(encoding="utf-8")
    detail = (ROOT / "gui/templates/capture_detail.html").read_text(encoding="utf-8")
    assert "r.links" in archive
    assert "d.safe_links" in detail
    assert "fromjson" not in detail
    assert 'href="/captures/discord"' in (ROOT / "gui/templates/captures.html").read_text(encoding="utf-8")
    matcher = (ROOT / "scripts/import/discord_match_audit.py").read_text(encoding="utf-8")
    assert "UPDATE discord_posts" not in matcher
