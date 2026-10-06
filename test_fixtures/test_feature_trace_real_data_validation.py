#!/usr/bin/env python3
from __future__ import annotations

from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_validation import TraceValidationCase, validate_case, validate_cases


def _trace_result(*, root_kind="entity", mode="identity", relationships=("IDENTITY_MATCH", "SERVER_ENTITY")):
    return {
        "root_kind": root_kind,
        "trace_mode": {"id": mode},
        "edges": [{"relationship": value} for value in relationships],
        "generator_plan": [],
        "generated_relationships": [],
    }


def test_real_data_validation_runner_statuses():
    original_resolve = feature_trace.resolve_query
    original_trace = feature_trace.trace
    try:
        resolutions = {
            "missing": {"status": "NOT_FOUND", "root": None},
            "ambiguous": {"status": "AMBIGUOUS", "root": None},
            "resolved": {"status": "RESOLVED", "root": "entity:123"},
            "gap": {"status": "RESOLVED", "root": "entity:456"},
        }

        def fake_resolve(_con, query, _catalog=None):
            return resolutions[query]

        def fake_trace(_con, root, _depth, _direction, _catalog=None, **kwargs):
            if root == "entity:456":
                return _trace_result(relationships=("IDENTITY_MATCH",))
            return _trace_result()

        feature_trace.resolve_query = fake_resolve
        feature_trace.trace = fake_trace

        cases = (
            TraceValidationCase("missing-case", "npc-id", query="missing"),
            TraceValidationCase("ambiguous-case", "npc-id", query="ambiguous"),
            TraceValidationCase("pass-case", "npc-id", query="resolved"),
            TraceValidationCase("gap-case", "npc-id", query="gap"),
            TraceValidationCase("exact-root", "npc-id", root="entity:789"),
        )
        report = validate_cases(object(), cases)
        rows = {row["case_id"]: row for row in report["cases"]}

        assert rows["missing-case"]["status"] == "UNAVAILABLE", rows
        assert rows["ambiguous-case"]["status"] == "AMBIGUOUS", rows
        assert rows["pass-case"]["status"] == "PASS", rows
        assert rows["gap-case"]["status"] == "CONTRACT_GAP", rows
        assert rows["exact-root"]["status"] == "PASS", rows
        assert report["counts"] == {
            "PASS": 2,
            "CONTRACT_GAP": 1,
            "UNAVAILABLE": 1,
            "AMBIGUOUS": 1,
        }, report
        assert report["attempted_contract_count"] == 3, report
        assert report["all_attempted_passed"] is False, report
        assert report["evidence_policy"]["missing_is_failure"] is False, report
        assert report["evidence_policy"]["ambiguous_is_auto_selected"] is False, report

        single = validate_case(object(), TraceValidationCase("one", "npc-id", query="resolved"))
        assert single["resolved_root"] == "entity:123", single
        assert single["evaluation"]["checks"]["mode"] is True, single
        assert single["evaluation"]["checks"]["root_kind"] is True, single
    finally:
        feature_trace.resolve_query = original_resolve
        feature_trace.trace = original_trace


def test_real_data_validation_case_guards():
    for kwargs in (
        {"case_id": "", "scenario_id": "npc-id", "query": "x"},
        {"case_id": "bad-scenario", "scenario_id": "does-not-exist", "query": "x"},
        {"case_id": "no-target", "scenario_id": "npc-id"},
        {"case_id": "two-targets", "scenario_id": "npc-id", "query": "x", "root": "entity:1"},
        {"case_id": "bad-depth", "scenario_id": "npc-id", "query": "x", "depth": 0},
    ):
        try:
            TraceValidationCase(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"case guard should reject {kwargs}")


def main():
    test_real_data_validation_case_guards()
    test_real_data_validation_runner_statuses()
    print("Feature Trace real-data validation runner regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
