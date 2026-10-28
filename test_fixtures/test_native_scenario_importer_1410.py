"""#1410 slice 5: native XiHeadless scenario importer. A synthetic git repo and a temporary SQLite file only;
nothing is run, no network, no live data."""
import json
import subprocess

import pytest

from workbench.server_admin.feature_testing import native_scenario_importer as imp, test_catalog as cat

OK = [{"name": "wait", "do": {"wait_ms": 3000}}, {"name": "in zone", "expect": {"zone": 235}}]
WITH_TIMEOUT = [{"name": "wait", "timeout_ms": 5000, "do": {"wait_ms": 3000}, "expect": {"zone": 235}}]
BAD = [{"name": "ok", "expect": {"zone": 235}}, {"name": "say", "do": {"say": "hi"}}]
TWO_ACTIONS = [{"name": "both", "do": {"talk_npc": 5, "walk_to": [1, 2]}}]
A06_OK = "docs/evidence/x/A06-1-probe/scenario.json"
FILES = {
    "scenarios/ok.json": OK,
    "scenarios/timed.json": WITH_TIMEOUT,
    "scenarios/bad.json": BAD,
    "scenarios/two.json": TWO_ACTIONS,
    A06_OK: OK,  # exact duplicate of scenarios/ok.json, on an A06 path (sorts first, so it is the kept one)
    "docs/evidence/x/A06-2-other/scenario.json": [{"name": "w", "do": {"wait_ms": 1}}],
    "scenarios/w1.json": [{"name": "w", "do": {"wait_ms": 5}}],
    "docs/schemas/scenario-evidence.schema.json": {"not": "a scenario"},
    "roles/scenario_like.json": OK,
}


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    _git(root, "init", "-q")
    for rel, value in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


@pytest.fixture()
def store(monkeypatch, tmp_path):
    db = tmp_path / "scratch.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(db))
    return db


def run(repo, **kw):
    root, sha = repo
    return imp.run_import(root, sha=sha, repo="example/fixture", **kw)


def test_discovers_only_scenario_paths_at_the_pinned_commit(repo):
    root, sha = repo
    assert imp.discover(root, sha) == sorted(p for p in FILES if p.startswith(("scenarios/", "docs/evidence/")))


def test_pin_must_be_the_exact_full_commit(repo):
    root, sha = repo
    with pytest.raises(ValueError, match="40-character"):
        imp.resolve_pin(root, sha[:10])
    with pytest.raises(ValueError):
        imp.resolve_pin(root, "0" * 40)


def test_reads_the_pinned_blob_not_the_working_tree(repo, store):
    root, sha = repo
    (root / A06_OK).write_text("[]", encoding="utf-8")  # an uncommitted edit must be ignored
    out = imp.run_import(root, sha=sha, repo="example/fixture")
    assert A06_OK in [i["path"] for i in out["imported"]]


def test_supported_scenario_becomes_a_draft_with_source_and_no_run(repo, store):
    out = run(repo)
    item = next(i for i in out["imported"] if i["path"] == A06_OK)
    entry = cat.get_entry(imp.FEATURE_ID, item["case_id"])
    rev = entry["revisions"][0]
    assert rev["source"] == f"import:example/fixture@{repo[1]}:{A06_OK}"
    assert entry["latest_state"] == "DRAFT" and entry["run_availability"] == "UNAVAILABLE"
    spec = rev["specification"]
    assert spec["execution_status"] == "design_only" and spec["runner"] == "unassigned"
    assert [s["name"] for s in spec["native_steps"]["steps"]] == ["wait", "in zone"]
    assert all("verdict" not in s for s in spec["native_steps"]["steps"])


def test_a_scenario_with_any_unsupported_step_is_rejected_whole_and_listed(repo, store):
    bad = next(r for r in run(repo)["rejected"] if r["path"] == "scenarios/bad.json")
    assert [s["name"] for s in bad["steps"]] == ["say"] and bad["steps"][0]["status"] == "UNSUPPORTED"
    assert cat.get_entry(imp.FEATURE_ID, "scenarios-bad") is None  # its supported first step was not imported alone


def test_two_actions_in_one_step_fail_closed(repo, store):
    two = next(r for r in run(repo)["rejected"] if r["path"] == "scenarios/two.json")
    assert "exactly one action" in two["steps"][0]["reasons"][0]


def test_timeout_ms_is_carried_by_default_and_the_flag_is_a_no_op(repo, store):
    out = run(repo)
    assert any(i["path"] == "scenarios/timed.json" for i in out["imported"])
    spec = cat.get_entry(imp.FEATURE_ID, "scenarios-timed")["revisions"][0]["specification"]
    step = spec["native_steps"]["steps"][0]
    assert step["timeout_ms"] == 5000 and "timeout_ms=" not in step["note"]
    assert not any("timeout_ms" in g for g in spec["authoring"]["blocking_gaps"])
    assert run(repo, carry_timeouts=True)["counts"]["imported"] + run(repo, carry_timeouts=True)["counts"]["unchanged"] >= 1


def test_round_trip_import_then_export_keeps_timeout_ms_unchanged(repo, store):
    from workbench.server_admin.feature_testing.typed_action_library import export_native_scenario
    run(repo)
    spec = cat.get_entry(imp.FEATURE_ID, "scenarios-timed")["revisions"][0]["specification"]
    assert export_native_scenario(spec["native_steps"]) == WITH_TIMEOUT


def test_exact_duplicates_are_merged_with_reasoning_and_recorded_in_the_draft(repo, store):
    out = run(repo)
    dup = out["deduplicated"][0]
    assert dup["kept"] == A06_OK and dup["merged_exact_duplicates"] == ["scenarios/ok.json"]
    assert "identical parsed step array" in dup["reason"]
    spec = cat.get_entry(imp.FEATURE_ID, "docs-evidence-x-A06-1-probe-scenario")["revisions"][0]["specification"]
    assert any("scenarios/ok.json" in g for g in spec["authoring"]["blocking_gaps"])
    assert cat.get_entry(imp.FEATURE_ID, "scenarios-ok") is None


def test_same_shape_different_content_is_reported_not_merged(repo, store):
    out = run(repo)
    near = [n for n in out["near_duplicate_shapes"] if "scenarios/w1.json" in n["paths"]]
    assert near and "docs/evidence/x/A06-2-other/scenario.json" in near[0]["paths"]
    assert cat.get_entry(imp.FEATURE_ID, "scenarios-w1") and cat.get_entry(imp.FEATURE_ID, "docs-evidence-x-A06-2-other-scenario")


def test_a06_is_an_annotation_with_open_owner_questions_and_no_verdict(repo, store):
    run(repo)
    entry = cat.get_entry(imp.FEATURE_ID, "docs-evidence-x-A06-2-other-scenario")
    rev = entry["revisions"][0]
    gaps = " ".join(rev["specification"]["authoring"]["blocking_gaps"])
    assert "a06-probe" in rev["tags"] and "NOT classified" in gaps and "OWNER QUESTION" in gaps
    assert entry["latest_state"] == "DRAFT" and entry["current_published_revision"] is None


def test_rerun_is_idempotent_and_dry_run_writes_nothing(repo, store):
    run(repo, apply=False)
    assert not store.exists()
    first = run(repo)
    again = run(repo)
    assert again["imported"] == [] and len(again["unchanged"]) == len(first["imported"]) > 0
    assert cat.get_entry(imp.FEATURE_ID, first["imported"][0]["case_id"])["revision_count"] == 1


def test_cli_refuses_existing_configured_or_relative_database(repo, tmp_path, monkeypatch):
    root, sha = repo
    base = ["--source-root", str(root), "--sha", sha]
    existing = tmp_path / "e.sqlite"
    existing.write_bytes(b"")
    with pytest.raises(SystemExit):
        imp.main(base + ["--scratch-db", str(existing)])
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "live.sqlite"))
    with pytest.raises(SystemExit):
        imp.main(base + ["--scratch-db", str(tmp_path / "live.sqlite"), "--allow-existing-db"])
    with pytest.raises(SystemExit):
        imp.main(base + ["--scratch-db", "relative.sqlite"])
    assert not (tmp_path / "live.sqlite").exists()


def test_cli_writes_report_and_only_the_scratch_db(repo, tmp_path, monkeypatch):
    root, sha = repo
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", raising=False)
    db, rep = tmp_path / "new.sqlite", tmp_path / "r.json"
    assert imp.main(["--source-root", str(root), "--sha", sha, "--scratch-db", str(db), "--report", str(rep)]) == 0
    assert json.loads(rep.read_text())["counts"]["files_examined"] == 7 and db.exists()
