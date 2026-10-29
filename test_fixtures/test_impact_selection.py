"""R6 #1210 WP2: impact selector. All repositories, paths and SHAs are synthetic format examples."""
import copy
import json
import random
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.impact_selection import select_candidates

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "test_fixtures" / "scenario_contract_v2_synthetic.json").read_text())["specification"]
REPO = "synthetic/dsp"
BASE, HEAD, OTHER = "a" * 40, "b" * 40, "c" * 40
STEP = TEMPLATE["steps"][0]["id"]


def source(path, lines=(10, 14), revision=BASE, repo=REPO, classification="dsp_source", ref="synthetic-source-1"):
    return {"ref": ref, "repository": repo, "path": path,
            "line_start": lines[0] if lines else None, "line_end": lines[1] if lines else None,
            "revision": revision, "classification": classification, "sha256": None}


def scenario(feature, case, *sources, associations=None):
    spec = copy.deepcopy(TEMPLATE)
    spec["feature_id"], spec["case_id"] = feature, case
    spec["contract_v2"]["sources"] = list(sources) or [source("scripts/unrelated_citation.lua")]
    if associations is not None:
        spec["contract_v2"]["source_associations"] = associations
    return spec


def plain(feature, case):
    spec = copy.deepcopy(TEMPLATE)
    spec["feature_id"], spec["case_id"] = feature, case
    del spec["contract_v2"]
    return spec


def change_set(*changes):
    return {"schema_version": 1, "repository": REPO, "base_sha": BASE, "head_sha": HEAD,
            "changes": [dict({"old_path": None, "hunks": None}, **c) for c in changes]}


def by_case(report):
    return {c["case_id"]: c for c in report["candidates"]}


def codes(candidate):
    return sorted({r["code"] for r in candidate["reasons"]})


# --- the four cases required by #1210 -------------------------------------------------------

def test_direct_inferred_unknown_and_deleted_cases():
    scenarios = [
        scenario("f_direct", "C-DIRECT", source("scripts/zones/Z/npcs/N.lua", (10, 14))),
        scenario("f_infer", "C-INFER", source("scripts/elsewhere.lua")),
        scenario("f_del", "C-DEL", source("scripts/old.lua", (1, 5))),
    ]
    links = [{"path": "scripts/globals/shared.lua", "feature_id": "f_infer",
              "edge": {"provider": "synthetic-index", "relationship": "IMPLEMENTS", "ref": "edge-1"}}]
    report = select_candidates(change_set(
        {"status": "M", "path": "scripts/zones/Z/npcs/N.lua", "hunks": [[12, 12]]},
        {"status": "D", "path": "scripts/old.lua"},
        {"status": "M", "path": "scripts/globals/shared.lua", "hunks": [[1, 1]]},
        {"status": "M", "path": "scripts/nobody_cites_this.lua", "hunks": [[3, 4]]}), scenarios, links)
    cases = by_case(report)
    assert cases["C-DIRECT"]["confidence"] == "DIRECT_SPAN" and codes(cases["C-DIRECT"]) == ["SPAN_OVERLAP"]
    assert cases["C-DIRECT"]["reasons"][0]["lines"] == [10, 14]
    assert cases["C-INFER"]["confidence"] == "INFERRED" and codes(cases["C-INFER"]) == ["TRACE_EDGE"]
    assert cases["C-INFER"]["reasons"][0]["trace_edge"]["ref"] == "edge-1"  # the cited edge is reported
    assert cases["C-DEL"]["confidence"] == "DIRECT_SPAN"
    assert cases["C-DEL"]["flags"] == ["SOURCE_REMOVED"] and "SPAN_REMOVED" in codes(cases["C-DEL"])
    assert report["unlinked_changes"] == [{"path": "scripts/nobody_cites_this.lua", "status": "M"}]
    assert report["launch"] == "NOT_PERFORMED"


# --- degradation rules: never claim a line-level link without evidence --------------------

@pytest.mark.parametrize("src,reason", [
    (source("scripts/a.lua", (10, 14), revision=None), "SOURCE_REVISION_UNPINNED"),
    (source("scripts/a.lua", (10, 14), revision=OTHER), "SOURCE_REVISION_DIFFERS"),
    (source("scripts/a.lua", None), "SOURCE_NO_LINE_SPAN"),
    (source("scripts/a.lua", (100, 110)), "NO_LINE_OVERLAP"),
])
def test_citations_without_line_evidence_stay_path_level(src, reason):
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]}),
                               [scenario("f", "C", src)])
    candidate = by_case(report)["C"]
    assert candidate["confidence"] == "DIRECT_PATH" and codes(candidate) == [reason]


def test_modified_file_without_hunks_is_path_level():
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua"}),
                               [scenario("f", "C", source("scripts/a.lua"))])
    assert codes(by_case(report)["C"]) == ["NO_HUNKS"]


def test_deleted_file_with_unpinned_citation_is_path_level_but_still_flagged():
    report = select_candidates(change_set({"status": "D", "path": "scripts/a.lua"}),
                               [scenario("f", "C", source("scripts/a.lua", revision=None))])
    candidate = by_case(report)["C"]
    assert candidate["confidence"] == "DIRECT_PATH" and candidate["flags"] == ["SOURCE_REMOVED"]
    assert "SOURCE_REVISION_UNPINNED" in codes(candidate)


def test_rename_matches_the_base_side_path_and_is_flagged_not_repointed():
    sc = [scenario("f", "C-OLD", source("scripts/a.lua", (1, 3))),
          scenario("f", "C-NEW", source("scripts/b.lua", (1, 3)))]
    report = select_candidates(change_set(
        {"status": "R", "path": "scripts/b.lua", "old_path": "scripts/a.lua"}), sc)
    cases = by_case(report)
    assert set(cases) == {"C-OLD"}  # a citation of the NEW name does not exist at base_sha
    assert cases["C-OLD"]["flags"] == ["SOURCE_RENAMED"] and cases["C-OLD"]["confidence"] == "DIRECT_PATH"
    assert report["unlinked_changes"] == []


def test_renamed_file_with_edits_can_still_reach_span_level():
    report = select_candidates(change_set(
        {"status": "R", "path": "scripts/b.lua", "old_path": "scripts/a.lua", "hunks": [[2, 2]]}),
        [scenario("f", "C", source("scripts/a.lua", (1, 3)))])
    candidate = by_case(report)["C"]
    assert candidate["confidence"] == "DIRECT_SPAN" and candidate["flags"] == ["SOURCE_RENAMED"]


def test_added_file_cited_by_a_scenario_is_path_level_only():
    report = select_candidates(change_set({"status": "A", "path": "scripts/new.lua"}),
                               [scenario("f", "C", source("scripts/new.lua"))])
    assert codes(by_case(report)["C"]) == ["PATH_ADDED_AFTER_BASE"]


def test_only_matching_repository_and_dsp_source_citations_count():
    sc = [scenario("f", "C-OTHER-REPO", source("scripts/a.lua", repo="other/repo")),
          scenario("f", "C-TOOLKIT", source("scripts/a.lua", classification="toolkit_code"))]
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]}), sc)
    assert report["candidates"] == []
    assert report["unlinked_changes"] == [{"path": "scripts/a.lua", "status": "M"}]
    assert report["cases_without_sources"] == ["f/C-OTHER-REPO", "f/C-TOOLKIT"]


# --- disclosure ------------------------------------------------------------------------------

def test_blind_spots_are_reported_not_hidden():
    bad = scenario("f", "C-BAD", source("scripts/a.lua"))
    bad["contract_v2"]["sources"][0]["line_start"] = 0  # fails contract validation
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]}),
                               [plain("f", "C-PLAIN"), bad])
    assert report["cases_without_sources"] == ["f/C-PLAIN"]
    assert [i["case_id"] for i in report["invalid_scenarios"]] == ["C-BAD"]
    assert report["candidates"] == []
    assert report["unlinked_changes"] == [{"path": "scripts/a.lua", "status": "M"}]


def test_trace_link_to_a_feature_without_cases_is_disclosed():
    links = [{"path": "scripts/a.lua", "feature_id": "ghost",
              "edge": {"provider": "p", "relationship": "r", "ref": "e"}}]
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua"}), [plain("f", "C")], links)
    assert report["candidates"] == [] and report["trace_links_without_cases"] == ["ghost"]
    assert report["unlinked_changes"] == []  # linked to a feature, just not to any case


def test_associations_are_reported_only_when_explicit():
    explicit = scenario("f", "C-ASSOC", source("scripts/a.lua"), associations=[
        {"scope": "step", "target_id": STEP, "source_refs": ["synthetic-source-1"]}])
    implicit = scenario("f", "C-NOASSOC", source("scripts/a.lua"))
    report = select_candidates(change_set({"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]}),
                               [explicit, implicit])
    cases = by_case(report)
    assert cases["C-ASSOC"]["reasons"][0]["associated_to"] == ["step:" + STEP]
    assert cases["C-NOASSOC"]["reasons"][0]["associated_to"] == ["UNKNOWN"]


# --- ordering, merging, determinism ----------------------------------------------------------

def test_ranking_and_merging():
    sc = [scenario("f", "A-PATH", source("scripts/a.lua", revision=None)),
          scenario("f", "B-SPAN", source("scripts/a.lua", (12, 12))),
          scenario("f", "C-REMOVED", source("scripts/gone.lua", (1, 2))),
          scenario("f", "D-TWO-FILES", source("scripts/a.lua", revision=None, ref="synthetic-source-1"),
                   source("scripts/b.lua", revision=None, ref="s2")),
          scenario("g", "E-INFER", source("scripts/zzz.lua"))]
    links = [{"path": "scripts/a.lua", "feature_id": "g",
              "edge": {"provider": "p", "relationship": "r", "ref": "e"}}]
    report = select_candidates(change_set(
        {"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]},
        {"status": "M", "path": "scripts/b.lua", "hunks": [[1, 1]]},
        {"status": "D", "path": "scripts/gone.lua"}), sc, links)
    assert [c["case_id"] for c in report["candidates"]] == [
        "C-REMOVED", "B-SPAN",            # span level; removed source first
        "D-TWO-FILES", "A-PATH",          # path level; more changed paths first, then name
        "E-INFER"]                        # inferred last
    assert by_case(report)["D-TWO-FILES"]["changed_path_count"] == 2
    # one case reached by a citation AND a trace edge keeps the strongest class, with both reasons
    merged = select_candidates(change_set({"status": "M", "path": "scripts/a.lua", "hunks": [[12, 12]]}),
                               [scenario("g", "C", source("scripts/a.lua", (12, 12)))], links)
    assert by_case(merged)["C"]["confidence"] == "DIRECT_SPAN" and codes(by_case(merged)["C"]) == ["SPAN_OVERLAP", "TRACE_EDGE"]


def test_output_is_deterministic_and_inputs_are_not_mutated():
    sc = [scenario("f", f"C{i}", source(f"scripts/f{i % 3}.lua", (i + 1, i + 2))) for i in range(6)]
    changes = [{"status": "M", "path": f"scripts/f{i}.lua", "hunks": [[2, 4]]} for i in range(3)] + [
        {"status": "D", "path": "scripts/x.lua"}]
    links = [{"path": "scripts/x.lua", "feature_id": "f",
              "edge": {"provider": "p", "relationship": "r", "ref": "e"}}]
    snapshot = copy.deepcopy((changes, sc, links))
    first = json.dumps(select_candidates(change_set(*changes), sc, links), sort_keys=True)
    assert (changes, sc, links) == snapshot
    for seed in range(5):
        rng = random.Random(seed)
        shuffled = (changes[:], sc[:], links[:])
        for part in shuffled:
            rng.shuffle(part)
        assert json.dumps(select_candidates(change_set(*shuffled[0]), shuffled[1], shuffled[2]), sort_keys=True) == first


def test_empty_change_set_yields_no_candidates():
    report = select_candidates(change_set(), [scenario("f", "C", source("scripts/a.lua"))])
    assert report["candidates"] == [] and report["unlinked_changes"] == []


# --- input validation ------------------------------------------------------------------------

def test_invalid_inputs_are_rejected():
    cs = change_set({"status": "M", "path": "scripts/a.lua"})
    with pytest.raises(ValueError):
        select_candidates(change_set({"status": "M", "path": "../a.lua"}), [])
    with pytest.raises(ValueError, match="must cite"):
        select_candidates(cs, [], [{"path": "scripts/a.lua", "feature_id": "f", "edge": {}}])
    with pytest.raises(ValueError, match="exactly"):
        select_candidates(cs, [], [{"path": "scripts/a.lua", "feature_id": "f"}])
    with pytest.raises(ValueError, match="duplicate scenario"):
        select_candidates(cs, [plain("f", "C"), plain("f", "C")])
    with pytest.raises(ValueError, match="list"):
        select_candidates(cs, "nope")
