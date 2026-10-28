"""R6 #1210 WP3: citation-pinning coverage report. Synthetic scenarios only."""
import copy
import json
import random
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.impact_coverage import source_citation_coverage

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "test_fixtures" / "scenario_contract_v2_synthetic.json").read_text())["specification"]
SHA = "a" * 40


def src(ref, revision=SHA, repo="synthetic/dsp", classification="dsp_source"):
    return {"ref": ref, "repository": repo, "path": f"scripts/{ref}.lua", "line_start": 1, "line_end": 2,
            "revision": revision, "classification": classification, "sha256": None}


def scenario(feature, case, *sources):
    spec = copy.deepcopy(TEMPLATE)
    spec["feature_id"], spec["case_id"] = feature, case
    spec["contract_v2"]["sources"] = list(sources)
    # the template's parameter cites "synthetic-source-1"; keep that ref resolvable
    if not any(s["ref"] == "synthetic-source-1" for s in sources):
        spec["contract_v2"]["parameters"][0]["source_refs"] = []
    return spec


def plain(feature, case):
    spec = copy.deepcopy(TEMPLATE)
    spec["feature_id"], spec["case_id"] = feature, case
    del spec["contract_v2"]
    return spec


def row(report, feature):
    return next(r for r in report["features"] if r["feature_id"] == feature)


def test_each_category_is_counted_per_feature():
    report = source_citation_coverage([
        scenario("f1", "FULL", src("s1"), src("s2")),
        scenario("f1", "PARTIAL", src("s1"), src("s2", revision=None)),
        scenario("f1", "UNPINNED", src("s1", revision=None)),
        scenario("f1", "NONE-V2", src("s1", classification="toolkit_code")),
        plain("f1", "NO-NAMESPACE"),
        scenario("f2", "FULL2", src("s1")),
    ])
    f1 = row(report, "f1")
    assert f1["fully_pinned"] == ["FULL"] and f1["partially_pinned"] == ["PARTIAL"]
    assert f1["unpinned_only"] == ["UNPINNED"]
    assert f1["no_dsp_source"] == ["NO-NAMESPACE", "NONE-V2"]
    assert f1["cases_total"] == 5 and f1["pinned_citations"] == 3 and f1["unpinned_citations"] == 2
    assert row(report, "f2")["fully_pinned"] == ["FULL2"]
    totals = report["totals"]
    assert totals["cases_total"] == 6 and totals["fully_pinned"] == 2 and totals["no_dsp_source"] == 2
    assert totals["pinned_citations"] == 4 and totals["unpinned_citations"] == 2
    assert [r["feature_id"] for r in report["features"]] == ["f1", "f2"]


def test_only_dsp_source_citations_count():
    report = source_citation_coverage([
        scenario("f", "C", src("s1", revision=None, classification="documentation"),
                 src("s2", revision=None, classification="client_dat"))])
    assert row(report, "f")["no_dsp_source"] == ["C"] and report["totals"]["unpinned_citations"] == 0


def test_repository_filter():
    sc = [scenario("f", "MIXED", src("s1", repo="synthetic/dsp"), src("s2", revision=None, repo="other/repo"))]
    assert row(source_citation_coverage(sc), "f")["partially_pinned"] == ["MIXED"]
    only_dsp = source_citation_coverage(sc, repository="synthetic/dsp")
    assert row(only_dsp, "f")["fully_pinned"] == ["MIXED"] and only_dsp["repository"] == "synthetic/dsp"
    assert row(source_citation_coverage(sc, repository="nobody/here"), "f")["no_dsp_source"] == ["MIXED"]


def test_invalid_scenarios_are_listed_not_counted():
    bad = scenario("f", "BAD", src("s1"))
    bad["contract_v2"]["sources"][0]["line_start"] = 0
    report = source_citation_coverage([bad, scenario("f", "OK", src("s1")), {"feature_id": "f"}])
    assert [(i["feature_id"], i["case_id"]) for i in report["invalid_scenarios"]] == [("f", "BAD"), ("f", None)]
    assert row(report, "f")["cases_total"] == 1 and report["totals"]["cases_total"] == 1


def test_empty_input_and_validation():
    report = source_citation_coverage([])
    assert report["features"] == [] and report["totals"]["cases_total"] == 0
    with pytest.raises(ValueError, match="duplicate scenario"):
        source_citation_coverage([plain("f", "C"), plain("f", "C")])
    with pytest.raises(ValueError, match="list"):
        source_citation_coverage("nope")


def test_deterministic_and_inputs_not_mutated():
    sc = [scenario("f", f"C{i}", src("s1", revision=None if i % 2 else SHA)) for i in range(6)]
    snapshot = copy.deepcopy(sc)
    first = json.dumps(source_citation_coverage(sc), sort_keys=True)
    assert sc == snapshot
    for seed in range(5):
        shuffled = sc[:]
        random.Random(seed).shuffle(shuffled)
        assert json.dumps(source_citation_coverage(shuffled), sort_keys=True) == first
