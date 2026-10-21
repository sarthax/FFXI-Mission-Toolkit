"""Synthetic-only, NONCANONICAL domain and evidence compatibility tests.

The domain snapshot contains exact cited source coordinates/lanes from staged
Agent E drafts, NOT gameplay observations or trusted source bytes. No
catalog import, mutating client/server calls or runner execution.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.scenario_contract_v2 import _validate_sources
from workbench.server_admin.feature_testing.scenario_contract_v2_adapters import (
    project_domain_case, project_identity_diagnostic, project_expected_candidate,
)
from workbench.server_admin.feature_testing.test_specifications import specification

FILE = Path(__file__).with_name("scenario_contract_v2_staging_adapter_synthetic.json")


def examples():
    fixture = json.loads(FILE.read_text(encoding="utf-8"))
    assert fixture["_fixture"].startswith("SYNTHETIC NONCANONICAL")
    return {row["domain"]: row for row in fixture["examples"]}


@pytest.mark.parametrize("domain,case_id,lane", [
    ("gardening", "GARD-01", "needs-mutation"),
    ("run_geo_unlock", "RG-01", "observe-now"),
    ("salvage", "SAL-01", "needs-readback"),
])
def test_staged_source_and_lane_projection_remains_untrusted(domain, case_id, lane):
    record = examples()[domain]
    original = deepcopy(record["staging"])
    view = project_domain_case(record["staging"], case_id)
    assert record["staging"] == original
    assert view["projection_contract"].endswith("_NONCANONICAL")
    assert view["case_id"] == case_id and view["execution_lane"] == lane
    assert view["execution_enabled"] is False
    assert view["canonical_import_allowed"] is False
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert view["staged_verdict"] == "NOT_RUN"
    assert view["oracles"] == [] and view["parameters"] == []
    assert view["oracle_projection"].startswith("UNKNOWN")
    assert len(view["step_requirements"]) == 4
    assert all(s["execution_gate"] == "blocked" and
               s["operation_class"] == "unknown" and
               s["approval_required"] is True for s in view["step_requirements"])
    assert all(s["sha256"] is None for s in view["sources"])
    _validate_sources(view["sources"])
    assert specification(domain, case_id) is None
    assert view["source_refs_original"], "Original citations are never discarded"
    assert view["readback_proposals_original"] == record["staging"]["cases"][0]["readback"]


def test_gardening_preserves_oracle_refs_and_pot_extra_readback_without_permission():
    row = examples()["gardening"]
    view = project_domain_case(row["staging"], "GARD-01")
    assert view["case_source_ref_ids"], "case-level oracle_sources is a list of citations"
    assert all(s["source_refs"] for s in view["step_requirements"])
    assert view["sources"][0]["revision"] == "330ea8f854cff47aae570aa95d6474f3225f5d49"
    assert view["readback_proposals_original"]["table"] == "char_inventory"
    assert "extra" in view["readback_proposals_original"]["columns"]
    assert view["execution_lane"] == "needs-mutation"


def test_run_geo_keeps_conditional_observe_now_but_not_unverified_unlock_success():
    view = project_domain_case(examples()["run_geo_unlock"]["staging"], "RG-01")
    assert view["execution_lane"] == "observe-now"
    assert "char_vars DwL_Prog,DwL_Declined" in view["readback_proposals_original"]["required"]
    assert all(s["execution_gate"] == "blocked" for s in view["step_requirements"])
    assert view["oracles"] == []
    assert view["sources"][0]["revision"] == "86d4467d446569c741d76d296e640c3b844ad844"


def test_salvage_instance_requires_readback_and_cannot_infer_stage_outcome():
    view = project_domain_case(examples()["salvage"]["staging"], "SAL-01")
    assert view["execution_lane"] == "needs-readback"
    assert "instance ID,stage,progress,expiry" in view["readback_proposals_original"]["missing"]
    assert view["oracles"] == []
    assert view["sources"][0]["path"].endswith("arrapago_remnants.lua")


def test_source_projection_deduplicates_only_exact_revision_path_and_range():
    row = deepcopy(examples()["run_geo_unlock"]["staging"])
    case = row["cases"][0]
    case["source_refs"].append(deepcopy(case["source_refs"][0]))
    one = project_domain_case(row, case["case_id"])
    two = project_domain_case(row, case["case_id"])
    assert one == two, "mapping and synthetic reference IDs are deterministic"
    assert len(one["sources"]) == 2
    assert len(one["source_refs_original"]) > len(one["sources"])
    assert one["case_source_ref_ids"].count(one["case_source_ref_ids"][0]) >= 2


@pytest.mark.parametrize("mutate", [
    lambda s: s["cases"][0].update(execution_authorized=True),
    lambda s: s["cases"][0].update(execution_status="verified_runner"),
    lambda s: s["cases"][0].update(lane="unrecognized-lane"),
    lambda s: s["cases"][0]["steps"][0].update(execution_authorized=True),
    lambda s: s["cases"][0]["steps"][0]["source_refs"][0].update(path="../evil.lua"),
    lambda s: s["cases"][0]["steps"][0]["source_refs"][0].update(commit="HEAD"),
])
def test_staged_unsafe_claims_conflicts_and_unpinned_sources_fail_closed(mutate):
    row = deepcopy(examples()["run_geo_unlock"]["staging"])
    mutate(row)
    with pytest.raises(ValueError):
        project_domain_case(row, "RG-01")


@pytest.mark.parametrize("classification,state,identity", [
    ("EXACT", "candidate", 7000),
    ("INFERRED", "candidate", 7000),
    ("AMBIGUOUS", "ambiguous", None),
    ("UNRESOLVED", "unresolved", None),
    ("UNSUPPORTED", "unresolved", None),
])
def test_agent_d_classification_is_never_automatically_source_verified(classification, state, identity):
    source = {"classification": classification, "identity": 7000,
              "source_identity_verified": False, "source_row_ref": "synthetic-indexed-row",
              "sha256": "a" * 64}
    original = deepcopy(source)
    result = project_identity_diagnostic(source, kind="npc")
    assert source == original
    assert result["classification_original"] == classification
    assert result["binding_state"] == state and result["identity_candidate"] == identity
    assert result["source_identity_verified"] is False
    assert result["execution_enabled"] is False
    assert result["source_diagnostic_original"] == original


def test_source_expected_candidate_never_promotes_normative_expectation():
    candidate = {
        "origin": "independent_dsp_source",
        "from_capture": False,
        "expected_candidate": "SYNTHETIC proposed outcome",
        "revision": "b" * 40,
        "sha256": "c" * 64,
    }
    copy = deepcopy(candidate)
    outcome = project_expected_candidate(candidate)
    assert candidate == copy and outcome["candidate_original"] == copy
    assert outcome["oracle_type"] == "unknown"
    assert outcome["source_refs"] == []
    assert outcome["confidence"] == "unknown"
    assert outcome["normative_expected"] is None and outcome["approved"] is False
    assert outcome["execution_enabled"] is False
    assert project_expected_candidate(None)["readiness"] == "UNKNOWN"


def test_unsupported_agent_d_oracle_and_identity_input_rejected():
    with pytest.raises(ValueError, match="classification"):
        project_identity_diagnostic({"classification": "VERIFIED"}, kind="npc")
    with pytest.raises(ValueError, match="identity"):
        project_identity_diagnostic({"classification": "EXACT"}, kind="opcode")
    with pytest.raises(ValueError, match="expectation"):
        project_expected_candidate("untrusted_not_an_object")
