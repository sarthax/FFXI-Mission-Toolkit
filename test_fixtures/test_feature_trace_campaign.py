"""Synthetic, offline regression for the real-object relevance baseline campaign gate.

NO real client, NPC IDs, repository captures, game SQL or DSP runtime are used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_feature_trace_campaign as campaign


def _build(tmp_path, *, case_status="REVIEWED", annotated=True):
    data = campaign.template()
    sha_a = "a" * 40
    sha_b = "b" * 40
    for i, case in enumerate(data["cases"]):
        if case_status != "REVIEWED":
            case["status"] = case_status
            continue
        case["status"] = "REVIEWED"
        case.pop("reason")
        case.update({
            "resolved_root_id": f"synthetic:root-{i}",
            "root_resolution": "unique",
            "reviewed_by": "synthetic reviewer",
            "toolkit_sha": sha_a,
            "server_sha": sha_b,
            "source_families": ["synthetic-source"],
            "trace_json": f"{i}-trace.json",
            "annotations_json": f"{i}-review.json",
        })
        trace = {
            "schema": "feature-trace-relevance-export-v1",
            "case_id": case["case_id"],
            "root": case["resolved_root_id"],
            "root_kind": case["root_kind"],
            "mode": case["mode"],
            "depth": 1,
            "direction": "both",
            "max_nodes": 500,
            "truncated": False,
            "edges": [
                {"id": "synthetic-script"},
                {"id": "synthetic-reference"},
            ],
            "edge_audit_ids": ["synthetic-script", "synthetic-reference"],
        }
        ann = {
            "initial_edge_ids": ["synthetic-script", "synthetic-reference"],
            "verified_edge_ids": ["synthetic-script", "synthetic-reference"] if annotated else ["synthetic-script"],
            "relevant_edge_ids": ["synthetic-script"],
            "required_edge_ids": ["synthetic-script"],
            "locator_edge_ids": ["synthetic-script"],
            "missing_required_paths": [],
        }
        (tmp_path / case["trace_json"]).write_text(json.dumps(trace), encoding="utf-8")
        (tmp_path / case["annotations_json"]).write_text(json.dumps(ann), encoding="utf-8")
    return data


def test_blank_campaign_never_claims_execution(tmp_path):
    blank = campaign.template()
    result = campaign.evaluate(blank, tmp_path)
    assert result["overall"] == "NOT_READY"
    assert result["counts"]["NOT_RUN"] == 3
    assert not any(c["scored"] for c in result["cases"])
    assert not any("PASS" in json.dumps(row) for row in result["cases"])


def test_mixed_blocked_not_run_remains_not_ready(tmp_path):
    data = campaign.template()
    data["cases"][0]["status"] = "BLOCKED"
    data["cases"][0]["reason"] = "synthetic missing graph"
    report = campaign.evaluate(data, tmp_path)
    assert report["counts"]["BLOCKED"] == 1
    assert report["counts"]["NOT_RUN"] == 2
    assert report["overall"] == "NOT_READY"


def test_reviewed_three_case_campaign_only_reports_measured(tmp_path):
    data = _build(tmp_path)
    report = campaign.evaluate(data, tmp_path)
    assert report["overall"] == "MEASURED_PENDING_OPERATOR_ACCEPTANCE"
    assert report["counts"]["MEASURED_REVIEW_REQUIRED"] == 3
    assert all(c["initial_edges"] == 2 for c in report["cases"])
    assert all(c["precision_verified_only"] == 0.5 for c in report["cases"])
    assert all(c["required_path_recall"] == 1.0 for c in report["cases"])
    assert all(c["locator_coverage_verified_initial"] == 0.5 for c in report["cases"])
    out = json.dumps(report)
    assert "synthetic:root" not in out
    assert "reviewer" not in out
    assert "-trace.json" not in out
    assert "synthetic-source" not in out


def test_incomplete_review_cannot_claim_measured_baseline(tmp_path):
    data = _build(tmp_path, annotated=False)
    result = campaign.evaluate(data, tmp_path)
    assert result["overall"] == "NOT_READY"
    assert result["counts"]["INCOMPLETE_ANNOTATIONS"] == 3
    assert all(c["unreviewed_initial_edges"] == 1 for c in result["cases"])


@pytest.mark.parametrize("change", ["duplicate", "wrong_mode", "wrong_kind", "missing_case"])
def test_manifest_requires_three_distinct_scenario_identities(tmp_path, change):
    data = campaign.template()
    if change == "duplicate":
        data["cases"][1]["case_id"] = "absolute-virtue"
    elif change == "wrong_mode":
        data["cases"][1]["mode"] = "implementation"
    elif change == "wrong_kind":
        data["cases"][0]["root_kind"] = "mission"
    elif change == "missing_case":
        data["cases"].pop()
    with pytest.raises(ValueError):
        campaign.evaluate(data, tmp_path)


@pytest.mark.parametrize("change", ["missing_sha", "ambiguous_root", "missing_review", "unknown_family",
                                     "invalid_annotation", "unfinished_with_files"])
def test_fail_closed_bad_evidence_and_provenance(tmp_path, change):
    data = _build(tmp_path)
    first = data["cases"][0]
    if change == "missing_sha":
        first["toolkit_sha"] = "no-revision"
    elif change == "ambiguous_root":
        first["root_resolution"] = "ambiguous"
    elif change == "missing_review":
        first["reviewed_by"] = ""
    elif change == "unknown_family":
        first["source_families"] = []
    elif change == "invalid_annotation":
        path = tmp_path / first["annotations_json"]
        a = json.loads(path.read_text())
        a["initial_edge_ids"] = ["wrong-source-id"]
        path.write_text(json.dumps(a))
    else:
        first["status"] = "NOT_RUN"
        first["reason"] = "synthetic blocked"
    with pytest.raises(ValueError):
        campaign.evaluate(data, tmp_path)


def test_template_cli_produces_only_not_run(capsys):
    assert campaign.main(["--template"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert set(v["case_id"] for v in body["cases"]) == set(campaign.CASES)
    assert all(row["status"] == "NOT_RUN" for row in body["cases"])


def test_full_cli_outputs_aggregate_without_private_paths(tmp_path, capsys):
    manifest = tmp_path / "private-baseline.json"
    manifest.write_text(json.dumps(_build(tmp_path)), encoding="utf-8")
    assert campaign.main([str(manifest)]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["overall"] == "MEASURED_PENDING_OPERATOR_ACCEPTANCE"
    assert str(tmp_path) not in output
    assert "private-baseline.json" not in output


@pytest.mark.parametrize("changed", [
    "case_id", "root", "root_kind", "mode", "schema", "depth",
    "direction", "max_nodes", "truncated", "edge_audit_ids", "edges",
])
def test_export_to_manifest_identity_and_edge_integrity_are_required(tmp_path, changed):
    data = _build(tmp_path)
    first = data["cases"][0]
    path = tmp_path / first["trace_json"]
    trace = json.loads(path.read_text(encoding="utf-8"))
    different = {
        "case_id": "wotg-cait-sith",
        "root": "synthetic:other",
        "root_kind": "mission",
        "mode": "mission",
        "schema": "unversioned-raw-json",
        "depth": 3,
        "direction": "sideways",
        "max_nodes": 10000,
        "truncated": "not-a-boolean",
        "edge_audit_ids": list(reversed(trace["edge_audit_ids"])),
        "edges": [{"id": "new-synthetic-edge"}],
    }
    trace[changed] = different[changed]
    path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError):
        campaign.evaluate(data, tmp_path)


def test_legacy_unbound_raw_graph_cannot_score_as_a_measured_campaign(tmp_path):
    data = _build(tmp_path)
    first = data["cases"][0]
    path = tmp_path / first["trace_json"]
    path.write_text(json.dumps({"edges": [{"id": "synthetic-script"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="versioned exact-root"):
        campaign.evaluate(data, tmp_path)


def test_swapped_file_paths_are_rejected_before_scoring(tmp_path):
    data = _build(tmp_path)
    data["cases"][0]["trace_json"], data["cases"][1]["trace_json"] = (
        data["cases"][1]["trace_json"], data["cases"][0]["trace_json"]
    )
    with pytest.raises(ValueError, match="exported case_id"):
        campaign.evaluate(data, tmp_path)


def test_one_canonical_root_cannot_be_reused_between_different_cases(tmp_path):
    data = _build(tmp_path)
    data["cases"][1]["resolved_root_id"] = data["cases"][0]["resolved_root_id"]
    with pytest.raises(ValueError, match="reuse one resolved root"):
        campaign.evaluate(data, tmp_path)


def test_real_export_metadata_is_reported_without_private_identity(tmp_path):
    data = _build(tmp_path)
    path = tmp_path / data["cases"][0]["trace_json"]
    trace = json.loads(path.read_text(encoding="utf-8"))
    trace["truncated"] = True
    path.write_text(json.dumps(trace), encoding="utf-8")
    report = campaign.evaluate(data, tmp_path)
    assert report["cases"][0]["export_truncated"] is True
    assert report["cases"][0]["export_depth"] == 1
    assert report["cases"][0]["export_edge_count"] == 2
    assert "synthetic:root" not in json.dumps(report)
    assert report["overall"] == "MEASURED_PENDING_OPERATOR_ACCEPTANCE"
    assert "PASS" not in json.dumps(report)


def test_duplicate_generated_evidence_disallows_a_fabricated_identity_ledger(tmp_path):
    data = _build(tmp_path)
    path = tmp_path / data["cases"][0]["trace_json"]
    trace = json.loads(path.read_text(encoding="utf-8"))
    edge = {
        "source_node": "synthetic:root-0",
        "target_node": "synthetic:target",
        "relationship": "SPAWN_USES_GROUP",
        "generator": "synthetic",
        "evidence": [{"row": "fixture"}],
    }
    trace["edges"] = [edge, dict(edge)]
    path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate edge"):
        campaign.evaluate(data, tmp_path)
