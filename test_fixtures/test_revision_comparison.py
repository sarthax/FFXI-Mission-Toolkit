"""R6 WP4 (#1211): cross-revision result comparison. Synthetic records, repositories and SHAs only."""
import copy
import json
import random

import pytest

from workbench.server_admin.feature_testing.revision_comparison import compare_revisions

OLD, NEW = "a" * 40, "b" * 40  # format examples only
DIGEST = "d" * 64


def rec(case, verdict, dsp=OLD, run="run-old", stage="behavior", evidence=None, observed="2026-10-01T00:00:00Z"):
    return {"run_id": run, "case_id": case, "feature_id": "feat", "stage": stage, "verdict": verdict,
            "observed_at": observed, "dsp_commit": dsp, "headless_commit": "h" * 40, "toolkit_commit": "t" * 40,
            "evidence": evidence if evidence is not None else {"note": "synthetic"}}


def ctx(cases, **over):
    base = {"definition_sha256": {f"feat/{c}": DIGEST for c in cases}, "environment_fingerprint": "env-1",
            "fixture_context": "fixture-1", "schema_version": 1}
    base.update(over)
    return base


def left(*records):
    return list(records)


def right(*records):
    return [dict(r, run_id="run-new", dsp_commit=NEW, observed_at="2026-10-02T00:00:00Z") for r in records]


def one(report, case):
    return next(c for c in report["comparisons"] if c["case_id"] == case)


CASES = ["P2F", "F2P", "P2U", "P2P", "F2F"]


def compare(old, new, lctx=None, rctx=None):
    cases = {r["case_id"] for r in old + new}
    return compare_revisions(old, right(*new), lctx if lctx is not None else ctx(cases),
                             rctx if rctx is not None else ctx(cases))


# --- the acceptance transitions (comparable pairs) -------------------------------------------

def test_core_transitions_when_runs_are_comparable():
    report = compare(
        [rec("P2F", "PASS"), rec("F2P", "FAIL"), rec("P2U", "PASS"), rec("P2P", "PASS"), rec("F2F", "FAIL"),
         rec("U2P", "UNKNOWN"), rec("U2U", "UNKNOWN"), rec("S", "SKIPPED")],
        [rec("P2F", "FAIL"), rec("F2P", "PASS"), rec("P2U", "UNKNOWN"), rec("P2P", "PASS"), rec("F2F", "FAIL"),
         rec("U2P", "PASS"), rec("U2U", "UNKNOWN"), rec("S", "PASS")])
    got = {c["case_id"]: c["transition"] for c in report["comparisons"]}
    assert got == {"P2F": "REGRESSION_CANDIDATE", "F2P": "FIXED_CANDIDATE", "P2U": "NOT_ESTABLISHED",
                   "P2P": "UNCHANGED", "F2F": "UNCHANGED", "U2P": "NOW_ESTABLISHED", "U2U": "STILL_UNKNOWN",
                   "S": "SKIPPED"}
    assert all(c["comparable"] for c in report["comparisons"])
    assert report["attribution"] == "NOT_ATTRIBUTED"
    assert report["transition_counts"]["REGRESSION_CANDIDATE"] == 1


def test_exact_revisions_and_run_ids_are_shown_side_by_side():
    row = one(compare([rec("P2F", "PASS")], [rec("P2F", "FAIL")]), "P2F")
    assert row["left"]["dsp_commit"] == OLD and row["right"]["dsp_commit"] == NEW
    assert row["left"]["run_id"] == "run-old" and row["right"]["run_id"] == "run-new"
    assert row["left"]["headless_commit"] == "h" * 40 and row["right"]["toolkit_commit"] == "t" * 40


# --- never conclude a regression from incomparable runs -------------------------------------

@pytest.mark.parametrize("rctx_over,expected", [
    ({"environment_fingerprint": "env-2"}, "ENVIRONMENT_MISMATCH"),
    ({"fixture_context": "fixture-2"}, "FIXTURE_CONTEXT_MISMATCH"),
    ({"schema_version": 2}, "SCHEMA_DRIFT"),
    ({"definition_sha256": {"feat/P2F": "e" * 64}}, "DEFINITION_CHANGED"),
])
def test_pass_to_fail_is_not_a_regression_when_the_context_differs(rctx_over, expected):
    report = compare([rec("P2F", "PASS")], [rec("P2F", "FAIL")], ctx(["P2F"]), ctx(["P2F"], **rctx_over))
    row = one(report, "P2F")
    assert row["transition"] == "NOT_COMPARABLE" and not row["comparable"] and expected in row["reasons"]
    assert row["left"]["verdict"] == "PASS" and row["right"]["verdict"] == "FAIL"  # still displayed
    assert "REGRESSION_CANDIDATE" not in report["transition_counts"]


def test_missing_context_is_not_comparable_never_assumed_equal():
    report = compare_revisions([rec("P2F", "PASS")], right(rec("P2F", "FAIL")))
    assert one(report, "P2F")["reasons"] == ["DEFINITION_DIGEST_MISSING", "ENVIRONMENT_FINGERPRINT_MISSING",
                                             "FIXTURE_CONTEXT_MISSING", "SCHEMA_VERSION_MISSING"]
    partial = ctx(["P2F"])
    del partial["environment_fingerprint"]
    only_right_has_env = compare_revisions([rec("P2F", "PASS")], right(rec("P2F", "FAIL")), partial, ctx(["P2F"]))
    assert "ENVIRONMENT_FINGERPRINT_MISSING" in one(only_right_has_env, "P2F")["reasons"]


def test_all_failing_conditions_are_listed_deterministically():
    report = compare([rec("P2F", "PASS")], [rec("P2F", "FAIL")], ctx(["P2F"]),
                     ctx(["P2F"], environment_fingerprint="x", schema_version=3, fixture_context="y"))
    assert one(report, "P2F")["reasons"] == ["ENVIRONMENT_MISMATCH", "FIXTURE_CONTEXT_MISMATCH", "SCHEMA_DRIFT"]


def test_same_revision_and_invalid_commits_are_not_a_revision_comparison():
    same = compare_revisions([rec("P2F", "PASS")], [rec("P2F", "FAIL", dsp=OLD)], ctx(["P2F"]), ctx(["P2F"]))
    assert one(same, "P2F")["reasons"] == ["SAME_DSP_REVISION"]
    bad = compare_revisions([rec("P2F", "PASS", dsp="main")], right(rec("P2F", "FAIL")), ctx(["P2F"]), ctx(["P2F"]))
    assert one(bad, "P2F")["reasons"] == ["DSP_COMMIT_INVALID_LEFT"]


# --- blocked results and missing evidence ---------------------------------------------------

@pytest.mark.parametrize("cls,expected", [
    ("ENVIRONMENT", "ENVIRONMENT_BLOCKED"), ("FIXTURE_ABSENT", "FIXTURE_ABSENT"),
    ("ORACLE_UNKNOWN", "ORACLE_UNKNOWN"), ("OTHER", "BLOCKED_OTHER")])
def test_blocked_is_classified_by_its_reason_class(cls, expected):
    row = one(compare([rec("C", "PASS")], [rec("C", "BLOCKED", evidence={"reason_class": cls})]), "C")
    assert row["transition"] == expected and row["right"]["reason_class"] == cls


def test_unclassified_blocked_rows_are_not_comparable_on_either_side():
    legacy = rec("C", "BLOCKED", evidence={"reason": "legacy free text"})
    assert one(compare([rec("C", "PASS")], [legacy]), "C")["reasons"] == ["UNCLASSIFIED_BLOCK_RIGHT"]
    assert one(compare([legacy], [rec("C", "PASS")]), "C")["reasons"] == ["UNCLASSIFIED_BLOCK_LEFT"]


def test_blocked_to_blocked_and_unblocked():
    blocked = {"reason_class": "ENVIRONMENT"}
    assert one(compare([rec("C", "BLOCKED", evidence=blocked)], [rec("C", "BLOCKED", evidence=blocked)]), "C")["transition"] == "STILL_BLOCKED"
    assert one(compare([rec("C", "BLOCKED", evidence=blocked)], [rec("C", "PASS")]), "C")["transition"] == "UNBLOCKED"


def test_missing_records_are_reported_not_called_regressions():
    report = compare_revisions([rec("GONE", "PASS"), rec("BOTH", "PASS")],
                               right(rec("BOTH", "PASS"), rec("NEW", "FAIL")), ctx(["GONE", "BOTH", "NEW"]),
                               ctx(["GONE", "BOTH", "NEW"]))
    got = {c["case_id"]: (c["transition"], c["reasons"]) for c in report["comparisons"]}
    assert got["GONE"] == ("NOT_ESTABLISHED", ["NO_RECORD_RIGHT"])
    assert got["NEW"] == ("NO_BASELINE", ["NO_RECORD_LEFT"])
    assert got["BOTH"][0] == "UNCHANGED"


# --- selection, determinism, validation -------------------------------------------------------

def test_latest_record_per_case_and_stage_wins_and_stages_stay_separate():
    old = [rec("C", "FAIL", run="run-a", observed="2026-09-01T00:00:00Z"),
           rec("C", "PASS", run="run-b", observed="2026-09-02T00:00:00Z"),
           rec("C", "FAIL", stage="gameplay")]
    new = [rec("C", "PASS", stage="gameplay")]
    report = compare_revisions(old, right(*new), ctx(["C"]), ctx(["C"]))
    by_stage = {c["stage"]: c for c in report["comparisons"]}
    assert by_stage["gameplay"]["transition"] == "FIXED_CANDIDATE"
    assert by_stage["behavior"]["left"]["run_id"] == "run-b" and by_stage["behavior"]["transition"] == "NOT_ESTABLISHED"


def test_deterministic_and_inputs_not_mutated():
    old = [rec(f"C{i}", "PASS") for i in range(6)]
    new = [rec(f"C{i}", "FAIL" if i % 2 else "PASS") for i in range(6)]
    lc = ctx([f"C{i}" for i in range(6)])
    snapshot = copy.deepcopy((old, new, lc))
    first = json.dumps(compare_revisions(old, right(*new), lc, lc), sort_keys=True)
    assert (old, new, lc) == snapshot
    for seed in range(5):
        a, b = old[:], right(*new)
        random.Random(seed).shuffle(a)
        random.Random(seed + 9).shuffle(b)
        assert json.dumps(compare_revisions(a, b, lc, lc), sort_keys=True) == first


def test_invalid_inputs_are_rejected():
    ok = ctx(["C"])
    with pytest.raises(ValueError, match="list"):
        compare_revisions("x", [], ok, ok)
    with pytest.raises(ValueError, match="missing required fields"):
        compare_revisions([{"case_id": "C"}], [], ok, ok)
    with pytest.raises(ValueError, match="unknown verdict"):
        compare_revisions([rec("C", "MAYBE")], [], ok, ok)
    with pytest.raises(ValueError, match="only"):
        compare_revisions([], [], {"surprise": 1}, ok)
    with pytest.raises(ValueError, match="64-hex"):
        compare_revisions([], [], {"definition_sha256": {"feat/C": "short"}}, ok)
    with pytest.raises(ValueError, match="schema_version"):
        compare_revisions([], [], {"schema_version": 0}, ok)
    with pytest.raises(ValueError, match="non-empty"):
        compare_revisions([], [], {"environment_fingerprint": " "}, ok)
