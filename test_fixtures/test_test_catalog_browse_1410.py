"""#1410: the Test Catalog browse pages show saved scenario revisions honestly and read-only.
Synthetic design-only specifications and a temporary SQLite file only; nothing is executed."""
import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.server_admin.feature_testing import catalog_view, router as ft_router, test_catalog as cat
from workbench.server_admin.feature_testing.test_specifications import specification

STEPS = {"library_version": 1, "steps": [
    {"name": "walk", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 4.2}},
    {"name": "again", "do": {"rest_hp": 50}},
    {"name": "zone check", "expect": {"zone": 231}}]}


def spec(case, **over):
    s = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    s["case_id"] = case
    s.update(over)
    return s


@pytest.fixture()
def store(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "catalog.sqlite"))
    for env in (ft_router.templates.env,):
        env.globals.setdefault("current_theme", lambda *a, **k: "dark")
        env.globals.setdefault("shell_context", lambda *a, **k: {})
    return tmp_path


def client(host="127.0.0.1"):
    app = FastAPI()
    app.include_router(ft_router.router)
    return TestClient(app, client=(host, 50000))


def tab(c, **params):
    query = "&".join(f"{k}={v}" for k, v in {"tab": "catalog", **params}.items())
    return c.get(f"/feature-testing?{query}")


def seed():
    cat.add_revision(spec("GRD-1", name="Gardening harvest check"), source="manual", tags=["gardening"])
    cat.add_revision(spec("INV-1", name="Bag versus database", purpose="Compares the Mog Safe"), source="draft:inv/INV-1", tags=["inventory", "read-only"])
    f = "inventory_observation"
    cat.record_state(f, "INV-1", 1, "VALIDATED_DESIGN")
    cat.record_state(f, "INV-1", 1, "PUBLISHED", "reviewed: shape only")
    cat.add_revision(spec("INV-1", name="Bag versus database v2", native_steps=STEPS), source="draft:inv/INV-1", tags=["inventory"], expected_latest=1)


# --- the list inside the Test catalog tab ------------------------------------------------------------------------------

def test_tab_says_so_when_nothing_is_saved_or_no_store_is_set(store, monkeypatch):
    assert "Nothing has been saved to the catalog yet." in tab(client()).text
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DRAFTS_DB")
    html = tab(client()).text
    assert "No catalog store is configured" in html and "Built-in test definitions" in html  # the old content is still there


def test_tab_is_local_only(store):
    seed()
    html = tab(client("203.0.113.9")).text
    assert "only shown to local readers" in html and "GRD-1" not in html


def test_tab_lists_saved_scenarios_with_state_and_published_revision(store):
    seed()
    html = tab(client()).text
    assert "2 saved scenarios" in html
    assert "/feature-testing/catalog-entry/inventory_observation/INV-1" in html and "Gardening harvest check" in html
    row = html[html.index("INV-1"):html.index("</tr>", html.index("INV-1"))]
    assert "r2 · DRAFT" in row and "r1" in row  # latest is an unreviewed draft; the published one is still r1
    assert "does not make a scenario runnable" in html and "Running is unavailable" in html


def test_search_filters_and_empty_match(store):
    seed()
    c = client()
    assert "GRD-1" in tab(c, cq="gardening").text and "INV-1" not in tab(c, cq="gardening").text
    assert "INV-1" in tab(c, ctag="inventory").text and "GRD-1" not in tab(c, ctag="inventory").text
    assert "No saved scenarios match these filters." in tab(c, cq="nothing-like-this").text
    assert "INV-1" in tab(c, cstate="DRAFT").text and "GRD-1" in tab(c, cstate="DRAFT").text
    assert "No saved scenarios match" in tab(c, cstate="ARCHIVED").text
    assert "GRD-1" in tab(c, cstate="NOT_A_STATE").text  # an unknown state is ignored, not an error page


def test_names_are_escaped(store):
    cat.add_revision(spec("XSS-1", name="<script>alert(1)</script>"), source="manual", tags=["x"])
    html = tab(client()).text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# --- the entry page ----------------------------------------------------------------------------------------------------

def entry(c, feature="inventory_observation", case="INV-1", **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return c.get(f"/feature-testing/catalog-entry/{feature}/{case}" + (f"?{query}" if query else ""))


def test_entry_defaults_to_the_current_published_revision_and_shows_history(store):
    seed()
    html = entry(client()).text
    assert "Revision r1 (current published)" in html and "Bag versus database" in html
    assert "VALIDATED_DESIGN → PUBLISHED" in html and "reviewed: shape only" in html
    assert "draft:inv/INV-1" in html and "Run availability: <strong>UNAVAILABLE</strong>" in html
    assert "Design-only." in html and "does not make the scenario runnable" in html
    assert "No typed steps are saved in this revision." in html  # r1 has none


def test_a_chosen_revision_shows_its_steps_as_when_then(store):
    seed()
    html = entry(client(), revision=2).text
    assert "Revision r2" in html and "(current published)" not in html
    for fragment in ("<strong>When</strong> walk to [1, 2]", "<strong>Then</strong> x near is 4.2",
                     "<strong>When</strong> rest hp 50", "<strong>Then</strong> zone is 231"):
        assert fragment in html, fragment
    assert "does not mean the runner can execute them" in html and "Full stored specification (JSON)" in html
    assert "That revision does not exist" in entry(client(), revision=99).text


def test_a_missing_entry_or_store_is_a_readable_404(store, monkeypatch):
    seed()
    missing = entry(client(), case="NOPE")
    assert missing.status_code == 404 and "No such catalog entry" in missing.text and "NOPE" in missing.text
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DRAFTS_DB")
    none = entry(client())
    assert none.status_code == 404 and "No catalog store is configured" in none.text


def test_the_entry_page_is_local_only(store):
    seed()
    assert entry(client("203.0.113.9")).status_code == 403


def test_nothing_published_is_stated_plainly(store):
    cat.add_revision(spec("ONLY-DRAFT"), source="manual")
    assert "None. No revision has been published." in entry(client(), case="ONLY-DRAFT").text


# --- describe_spec / native_step_lines tolerate odd shapes ---------------------------------------------------------------

def test_describe_spec_never_crashes_on_odd_shapes():
    for odd in (None, "x", [], {}, {"preconditions": "nope", "assertions": 5, "behavior": [], "native_steps": 3},
                {"native_steps": {"steps": [None, {"do": {"a": 1, "b": 2}}, {"do": "no"}, {"expect": {"zone": 1}}]}}):
        out = catalog_view.describe_spec(odd)
        assert isinstance(out["steps"], list) and isinstance(out["preconditions"], list)
    multi = catalog_view.native_step_lines({"steps": [{"name": "n", "do": {"a": 1, "b": 2}, "expect": {"zone": 1, "hpp": 2}}]})
    assert [l["keyword"] for l in multi] == ["When", "And", "Then", "And"]  # no key of a multi-key step is hidden
    lines = catalog_view.native_step_lines(STEPS)
    assert [l["keyword"] for l in lines] == ["When", "Then", "When", "Then"]
    assert catalog_view.native_step_lines({"steps": [{"do": {"a": 1}}, {"do": {"b": 2}}]})[1]["keyword"] == "And"


def test_hostile_text_in_a_stored_revision_is_escaped_on_the_entry_page(store, monkeypatch):
    """The API will not store such text, but the page must not trust the store: a row written directly is shown as text."""
    seed()
    real = cat.get_entry
    def tampered(feature_id, case_id):
        e = real(feature_id, case_id)
        s = e["revisions"][1]["specification"]
        s["native_steps"] = {"library_version": 1, "steps": [{"name": "<img src=x onerror=1>", "do": {"talk_npc": "<script>1</script>"}}]}
        s["preconditions"] = ["<b>pre</b>"]
        e["revisions"][1]["source"] = "<i>src</i>"
        return e
    monkeypatch.setattr(cat, "get_entry", tampered)
    html = entry(client(), revision=2).text
    for raw in ("<script>1</script>", "<img src=x onerror=1>", "<b>pre</b>", "<i>src</i>"):
        assert raw not in html, raw
    assert "&lt;script&gt;1&lt;/script&gt;" in html and "&lt;b&gt;pre&lt;/b&gt;" in html


# --- review controls on the entry page ---------------------------------------------------------------------------------

def buttons(html):
    import re
    return re.findall(r'data-state="([A-Z_]+)"', html)


def test_only_the_next_review_steps_are_offered_for_the_shown_revision(store):
    seed()  # INV-1 r1 PUBLISHED, r2 DRAFT; GRD-1 r1 DRAFT
    f, c = "inventory_observation", "GRD-1"
    draft = entry(client(), case="GRD-1").text
    assert buttons(draft) == ["VALIDATED_DESIGN", "ARCHIVED"] and "Publish (record review decision)" not in draft
    assert "does not make it runnable and does not show it is correct" in draft and 'id="ce-token"' in draft and 'id="ce-note"' in draft
    cat.record_state(f, c, 1, "VALIDATED_DESIGN")
    assert buttons(entry(client(), case="GRD-1").text) == ["PUBLISHED", "ARCHIVED"]
    cat.record_state(f, c, 1, "PUBLISHED", "ok")
    assert buttons(entry(client(), case="GRD-1").text) == ["ARCHIVED"]
    cat.record_state(f, c, 1, "ARCHIVED", "old")
    done = entry(client(), case="GRD-1").text
    assert buttons(done) == [] and "there is no further review step" in done and 'id="ce-token"' not in done


def test_the_controls_follow_the_shown_revision_not_the_latest(store):
    seed()
    assert buttons(entry(client(), revision=1).text) == ["ARCHIVED"]  # r1 is PUBLISHED
    assert buttons(entry(client(), revision=2).text) == ["VALIDATED_DESIGN", "ARCHIVED"]  # r2 is a fresh DRAFT


def test_publish_and_archive_ask_for_confirmation_and_carry_the_revision(store):
    seed()
    cat.record_state("inventory_observation", "INV-1", 2, "VALIDATED_DESIGN")
    html = entry(client(), revision=2).text
    assert 'data-revision="2"' in html and 'data-feature="inventory_observation"' in html and 'data-case="INV-1"' in html
    assert "Publish r2 of INV-1? This records your review decision. It does not make the scenario runnable." in html
    assert "/static/catalog_entry_review.js" in html


def test_allowed_next_is_the_table_the_store_enforces():
    for state in cat.STATES:
        assert cat.allowed_next(state) == cat._NEXT[state]
    assert cat.allowed_next("NOT_A_STATE") == ()


def test_entry_page_lists_execution_path_blockers_1412(store):
    seed()
    html = entry(client(), revision=2).text
    assert 'id="ft-ce-blockers"' in html and "<strong>MCP task start:</strong> BLOCKED" in html
    for key in ("do.walk_to", "expect.x_near", "do.rest_hp", "expect.zone"):
        assert f"<code>{key}</code>" in html, key
    assert "scenario_resource_actions_not_yet_supported" in html and "nothing was executed" in html
    assert "Execution path blockers" not in entry(client(), revision=1).text  # r1 has no typed steps
