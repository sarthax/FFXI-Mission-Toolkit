"""#1410: the versioned, searchable test catalog. Synthetic design-only specifications and a temporary SQLite file only;
nothing is executed, published to a runner or sent anywhere."""
import copy
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.server_admin.feature_testing import router as ft_router, test_catalog as cat
from workbench.server_admin.feature_testing.test_specifications import specification

TOKEN = "throwaway-operator-token-0123456789abcdef"


def spec(case="CAT-1", **over):
    s = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    s["case_id"] = case
    s.update(over)
    return s


@pytest.fixture()
def store(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "catalog.sqlite"))
    return tmp_path / "catalog.sqlite"


# --- revisions are immutable and linear ----------------------------------------------------------------------------

def test_a_new_entry_starts_as_a_draft_revision_with_hashes_and_source(store):
    out = cat.add_revision(spec(), source="draft:INV/CAT-1", tags=["inventory", "read-only"])
    assert out == {"feature_id": "inventory_observation", "case_id": "CAT-1", "revision": 1, "state": "DRAFT",
                   "execution_enabled": False, "run_availability": "UNAVAILABLE"}
    entry = cat.get_entry("inventory_observation", "CAT-1")
    rev = entry["revisions"][0]
    assert len(rev["content_sha256"]) == 64 and len(rev["base_spec_sha256"]) == 64
    assert rev["source"] == "draft:INV/CAT-1" and rev["tags"] == ["inventory", "read-only"]
    assert rev["events"][0]["state"] == "DRAFT" and entry["current_published_revision"] is None


def test_changing_content_means_a_new_revision_never_an_edit(store):
    cat.add_revision(spec(), source="manual")
    second = spec(name="Renamed")
    assert cat.add_revision(second, source="manual", expected_latest=1)["revision"] == 2
    entry = cat.get_entry("inventory_observation", "CAT-1")
    assert [r["specification"]["name"] for r in entry["revisions"]] == ["Inventory client versus persisted DSP", "Renamed"]
    assert entry["revisions"][0]["content_sha256"] != entry["revisions"][1]["content_sha256"]


def test_adding_needs_the_latest_revision_you_saw(store):
    cat.add_revision(spec(), source="manual")
    with pytest.raises(ValueError, match="revision conflict"):
        cat.add_revision(spec(name="B"), source="manual", expected_latest=0)
    with pytest.raises(ValueError, match="revision conflict"):
        cat.add_revision(spec(name="B"), source="manual", expected_latest=5)
    assert cat.get_entry("inventory_observation", "CAT-1")["revision_count"] == 1


def test_history_cannot_be_rewritten_even_with_a_direct_statement(store):
    cat.add_revision(spec(), source="manual")
    conn = sqlite3.connect(str(store))
    for statement in ("UPDATE test_catalog_revisions SET content='{}'", "DELETE FROM test_catalog_revisions",
                      "UPDATE test_catalog_events SET state='PUBLISHED'", "DELETE FROM test_catalog_events"):
        with pytest.raises(sqlite3.DatabaseError, match="immutable|append-only"):
            conn.execute(statement)
    assert cat.get_entry("inventory_observation", "CAT-1")["latest_state"] == "DRAFT"


# --- nothing here can claim to run ---------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [{"runner": "verified_runner"}, {"execution_status": "verified_runner"},
                                    {"execution_status": "published"}])
def test_revisions_must_stay_design_only_and_unassigned(store, change):
    with pytest.raises(ValueError, match="design_only"):
        cat.add_revision(spec(**change), source="manual")
    assert cat.list_entries()["total"] == 0


def test_invalid_input_writes_nothing(store):
    bad = spec()
    bad["assertions"] = "nope"
    for payload, kwargs in ((bad, {}), (spec(), {"source": "http://x"}), (spec(), {"source": "manual", "tags": ["Bad Tag"]}),
                            (spec(), {"source": "manual", "tags": ["a"] * 11}), ("not a dict", {}),
                            (spec(case="bad id!"), {})):
        kwargs.setdefault("source", "manual")
        with pytest.raises(ValueError):
            cat.add_revision(payload, **kwargs)
    big = spec()
    big["cleanup"] = ["x" * 200] * 400
    with pytest.raises(ValueError, match="32KiB|invalid|cleanup"):
        cat.add_revision(big, source="manual")
    assert cat.list_entries()["total"] == 0


# --- review states --------------------------------------------------------------------------------------------------

def test_states_only_move_forward_and_publishing_needs_a_reviewer_note(store):
    cat.add_revision(spec(), source="manual")
    f, c = "inventory_observation", "CAT-1"
    with pytest.raises(ValueError, match="cannot move to PUBLISHED"):
        cat.record_state(f, c, 1, "PUBLISHED", "skipping validation")
    cat.record_state(f, c, 1, "VALIDATED_DESIGN")
    with pytest.raises(ValueError, match="note is required"):
        cat.record_state(f, c, 1, "PUBLISHED", "   ")
    out = cat.record_state(f, c, 1, "PUBLISHED", "reviewed by the owner; design only")
    assert out["state"] == "PUBLISHED" and out["run_availability"] == "UNAVAILABLE" and out["execution_enabled"] is False
    with pytest.raises(ValueError, match="cannot move to VALIDATED_DESIGN"):
        cat.record_state(f, c, 1, "VALIDATED_DESIGN")
    cat.record_state(f, c, 1, "ARCHIVED", "superseded")
    with pytest.raises(ValueError, match="cannot move"):
        cat.record_state(f, c, 1, "PUBLISHED", "again")
    states = [e["state"] for e in cat.get_entry(f, c)["revisions"][0]["events"]]
    assert states == ["DRAFT", "VALIDATED_DESIGN", "PUBLISHED", "ARCHIVED"]  # the whole history is kept


def test_unknown_revision_state_or_note_is_refused(store):
    cat.add_revision(spec(), source="manual")
    f, c = "inventory_observation", "CAT-1"
    for args in ((f, c, 9, "VALIDATED_DESIGN"), (f, c, 1, "RUNNABLE"), (f, c, 0, "ARCHIVED"), (f, c, True, "ARCHIVED")):
        with pytest.raises(ValueError):
            cat.record_state(*args)
    with pytest.raises(ValueError, match="note"):
        cat.record_state(f, c, 1, "ARCHIVED", "x" * 301)
    assert cat.get_entry(f, c)["latest_state"] == "DRAFT"


def test_a_stored_revision_is_rechecked_before_it_advances(store, monkeypatch):
    cat.add_revision(spec(), source="manual")
    def stricter(spec_):
        raise ValueError("a rule added after this revision was stored")
    monkeypatch.setattr(cat, "validate_spec", stricter)
    with pytest.raises(ValueError, match="rule added after"):
        cat.record_state("inventory_observation", "CAT-1", 1, "VALIDATED_DESIGN")
    assert cat.get_entry("inventory_observation", "CAT-1")["latest_state"] == "DRAFT"


def test_current_published_is_the_latest_published_and_a_revert_is_a_new_revision(store):
    f, c = "inventory_observation", "CAT-1"
    cat.add_revision(spec(name="v1"), source="manual")
    cat.record_state(f, c, 1, "VALIDATED_DESIGN"); cat.record_state(f, c, 1, "PUBLISHED", "ok v1")
    cat.add_revision(spec(name="v2"), source="manual", expected_latest=1)
    cat.record_state(f, c, 2, "VALIDATED_DESIGN"); cat.record_state(f, c, 2, "PUBLISHED", "ok v2")
    assert cat.get_entry(f, c)["current_published_revision"] == 2
    cat.add_revision(spec(name="v1"), source="manual:revert of 1", expected_latest=2)  # revert = new revision, same content
    entry = cat.get_entry(f, c)
    assert entry["latest_revision"] == 3 and entry["latest_state"] == "DRAFT"
    assert entry["current_published_revision"] == 2  # an unreviewed revert is not published
    assert entry["revisions"][2]["content_sha256"] == entry["revisions"][0]["content_sha256"]


# --- search and categories ------------------------------------------------------------------------------------------

def test_search_by_text_feature_tag_and_state(store):
    cat.add_revision(spec("A-1", name="Gardening harvest check"), source="manual", tags=["gardening", "read-only"])
    cat.add_revision(spec("B-1", name="Bag versus database"), source="manual", tags=["inventory"])
    cat.add_revision(spec("C-1", name="Another inventory case", purpose="Compares the Mog Safe"), source="manual", tags=["inventory"])
    cat.record_state("inventory_observation", "B-1", 1, "VALIDATED_DESIGN")
    names = lambda **kw: [e["case_id"] for e in cat.list_entries(**kw)["entries"]]
    assert names() == ["A-1", "B-1", "C-1"]
    assert names(q="GARDENING") == ["A-1"] and names(q="mog safe") == ["C-1"] and names(q="a-1") == ["A-1"]
    assert names(tag="inventory") == ["B-1", "C-1"] and names(state="VALIDATED_DESIGN") == ["B-1"]
    assert names(feature_id="nothing") == [] and names(q="zzz-nothing") == []
    assert cat.list_entries(limit=1, offset=1)["entries"][0]["case_id"] == "B-1" and cat.list_entries(limit=1)["total"] == 3
    for bad in ({"limit": 0}, {"limit": 201}, {"offset": -1}, {"state": "RUNNABLE"}):
        with pytest.raises(ValueError):
            cat.list_entries(**bad)


def test_a_missing_store_setting_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", raising=False)
    with pytest.raises(ValueError, match="MISSION_TOOLKIT_TEST_DRAFTS_DB"):
        cat.list_entries()


# --- routes ----------------------------------------------------------------------------------------------------------

@pytest.fixture()
def client(store, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", TOKEN)
    app = FastAPI()
    app.include_router(ft_router.router)
    return TestClient(app, client=("127.0.0.1", 50000))


def test_reads_are_local_and_open_but_writes_need_the_operator_token(client):
    body = {"specification": spec(), "source": "manual", "tags": ["inventory"]}
    assert client.post("/feature-testing/test-catalog/revisions", json=body).status_code in (401, 403)
    assert client.post("/feature-testing/test-catalog/revisions", json=body, headers={"x-test-operator-token": "wrong"}).status_code in (401, 403)
    ok = client.post("/feature-testing/test-catalog/revisions", json=body, headers={"x-test-operator-token": TOKEN})
    assert ok.status_code == 200 and ok.json()["revision"] == 1 and ok.json()["execution_enabled"] is False
    listing = client.get("/feature-testing/test-catalog?q=inventory").json()
    assert listing["total"] == 1 and listing["entries"][0]["run_availability"] == "UNAVAILABLE"
    assert client.get("/feature-testing/test-catalog/inventory_observation/CAT-1").json()["revisions"][0]["source"] == "manual"
    assert client.get("/feature-testing/test-catalog/inventory_observation/NOPE").status_code == 404


def test_state_and_conflict_responses(client):
    h = {"x-test-operator-token": TOKEN}
    body = {"specification": spec(), "source": "manual"}
    client.post("/feature-testing/test-catalog/revisions", json=body, headers=h)
    conflict = client.post("/feature-testing/test-catalog/revisions", json=body, headers=h)  # expected_latest 0, but 1 exists
    assert conflict.status_code == 409 and "revision conflict" in conflict.json()["detail"]
    state = {"feature_id": "inventory_observation", "case_id": "CAT-1", "revision": 1, "state": "PUBLISHED", "note": "x"}
    assert client.post("/feature-testing/test-catalog/state", json=state, headers=h).status_code == 400  # skips validation
    assert client.post("/feature-testing/test-catalog/state", json=state, headers={}).status_code in (401, 403)
    client.post("/feature-testing/test-catalog/state", json={**state, "state": "VALIDATED_DESIGN"}, headers=h)
    assert client.post("/feature-testing/test-catalog/state", json=state, headers=h).status_code == 200


def test_remote_clients_are_refused_for_reads(store, monkeypatch):
    app = FastAPI()
    app.include_router(ft_router.router)
    remote = TestClient(app, client=("203.0.113.9", 50000))
    assert remote.get("/feature-testing/test-catalog").status_code == 403


def test_a_missing_store_is_a_503_not_a_crash(client, monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DRAFTS_DB")
    assert client.get("/feature-testing/test-catalog").status_code == 503


# --- add a saved draft to the catalog ---------------------------------------------------------------------------------

from workbench.server_admin.feature_testing import spec_drafts  # noqa: E402


def saved_draft(case="DRF-1", **over):
    spec_drafts.save_draft(spec(case, **over), 0)
    return spec_drafts.get_draft("inventory_observation", case)


def test_a_saved_draft_becomes_the_next_catalog_revision_with_a_true_source(store):
    draft = saved_draft()
    out = cat.add_from_draft("inventory_observation", "DRF-1", draft["revision"], tags=["inventory"])
    assert out["revision"] == 1 and out["state"] == "DRAFT" and out["run_availability"] == "UNAVAILABLE"
    rev = cat.get_entry("inventory_observation", "DRF-1")["revisions"][0]
    assert rev["source"] == "draft:inventory_observation/DRF-1@r1" and rev["tags"] == ["inventory"]
    assert rev["specification"] == draft["specification"]  # the stored draft, not anything the caller sent
    spec_drafts.save_draft(spec("DRF-1", name="Edited"), 1)
    assert cat.add_from_draft("inventory_observation", "DRF-1", 2)["revision"] == 2


def test_a_draft_that_moved_on_or_does_not_exist_is_not_added(store):
    saved_draft()
    spec_drafts.save_draft(spec("DRF-1", name="Edited"), 1)  # the draft is now revision 2
    with pytest.raises(ValueError, match="draft conflict"):
        cat.add_from_draft("inventory_observation", "DRF-1", 1)
    with pytest.raises(ValueError, match="no such saved draft"):
        cat.add_from_draft("inventory_observation", "NOPE", 1)
    for bad in (0, -1, True, "1"):
        with pytest.raises(ValueError):
            cat.add_from_draft("inventory_observation", "DRF-1", bad)
    assert cat.list_entries()["total"] == 0


def test_the_same_saved_content_is_not_added_twice(store):
    saved_draft()
    cat.add_from_draft("inventory_observation", "DRF-1", 1)
    with pytest.raises(ValueError, match="already the latest catalog revision"):
        cat.add_from_draft("inventory_observation", "DRF-1", 1)
    assert cat.get_entry("inventory_observation", "DRF-1")["revision_count"] == 1


def test_a_draft_that_breaks_a_catalog_rule_is_refused(store):
    saved_draft()
    with pytest.raises(ValueError, match="tag"):
        cat.add_from_draft("inventory_observation", "DRF-1", 1, tags=["Bad Tag"])
    assert cat.list_entries()["total"] == 0


def test_from_draft_route_needs_the_token_and_maps_errors(client):
    saved_draft()
    body = {"feature_id": "inventory_observation", "case_id": "DRF-1", "draft_revision": 1, "tags": ["inventory"]}
    url = "/feature-testing/test-catalog/from-draft"
    h = {"x-test-operator-token": TOKEN}
    assert client.post(url, json=body).status_code in (401, 403)
    ok = client.post(url, json=body, headers=h)
    assert ok.status_code == 200 and ok.json()["revision"] == 1 and ok.json()["execution_enabled"] is False
    assert client.post(url, json=body, headers=h).status_code == 409  # already the latest
    spec_drafts.save_draft(spec("DRF-1", name="Edited"), 1)
    assert client.post(url, json=body, headers=h).status_code == 409  # the draft moved on (now r2)
    assert client.post(url, json={**body, "draft_revision": 2}, headers=h).json()["revision"] == 2
    assert client.post(url, json={**body, "case_id": "NOPE"}, headers=h).status_code == 400
    assert client.get("/feature-testing/test-catalog/inventory_observation/DRF-1").json()["revision_count"] == 2


def test_entry_revision_reports_execution_path_blockers_1412(store):
    native = {"library_version": 1, "steps": [{"name": "Wait", "do": {"wait_ms": 100}},
                                              {"name": "Zone", "expect": {"zone": 80}}]}
    cat.add_revision(spec(native_steps=native), source="manual")
    rev = cat.get_entry("inventory_observation", "CAT-1")["revisions"][0]
    blockers = rev["execution_path_blockers"]
    assert blockers["mcp_task_start"]["status"] == "BLOCKED"
    assert [b["key"] for b in blockers["mcp_task_start"]["blocked_steps"]] == ["zone"]
    assert blockers["execution_enabled"] is False
