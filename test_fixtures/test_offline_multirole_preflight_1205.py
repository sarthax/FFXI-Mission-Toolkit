"""SYNTHETIC R4 role-preflight fixtures; no bot/pool/gameplay fixtures or IDs."""
from copy import deepcopy
import json

import pytest

from workbench.server_admin.feature_testing.offline_multirole_preflight_1205 import (
    FORMAT, offline_role_preflight,
)


def single():
    return {
        "schema": FORMAT,
        "feature_id": "synthetic_feature",
        "scenario_id": "synthetic_solo_case",
        "required_role_kinds": ["leader"],
        "roles": [
            {"id": "leader_one", "kind": "leader",
             "required_capabilities": ["observe_state"]},
        ],
        "checkpoints": [
            {"id": "first_observation", "required_role_ids": ["leader_one"],
             "depends_on": [], "oracle_id": "synthetic_state_oracle"},
        ],
    }


def triple():
    model = single()
    model["scenario_id"] = "synthetic_triple_case"
    model["required_role_kinds"] = ["leader", "healer", "dps"]
    model["roles"] += [
        {"id": "healer_one", "kind": "healer",
         "required_capabilities": ["observe_ally_hp"]},
        {"id": "dps_one", "kind": "dps",
         "required_capabilities": ["observe_claim"]},
    ]
    model["checkpoints"].append({
        "id": "party_checkpoint", "required_role_ids": [
            "leader_one", "healer_one", "dps_one"],
        "depends_on": ["first_observation"],
        "oracle_id": "synthetic_party_oracle",
    })
    return model


def fully_reported():
    return {
        "available_role_kinds": ["leader", "healer", "dps"],
        "available_pool_slots": 3,
        "observed_capabilities": [
            "observe_state", "observe_ally_hp", "observe_claim"],
        "lease_status": "REPORTED_AVAILABLE",
        "cleanup_status": "REPORTED_COMPLETE",
        "oracle_statuses": {
            "synthetic_state_oracle": "REPORTED_COVERED",
            "synthetic_party_oracle": "REPORTED_COVERED",
        },
    }


def states(out):
    return {x["id"]: x["state"] for x in out["checks"]}


def always_nonexecuting(out):
    assert out["execution_enabled"] is False
    assert out["task_admission_supported"] is False
    assert out["lease_acquisition_supported"] is False
    assert out["persisted"] is False
    assert out["execution_status"] == "NOT_AUTHORIZED"
    assert out["observed_gameplay_verdict"] == "UNKNOWN"
    assert out["oracle_authority"] == "NOT_ESTABLISHED"
    assert out["claims_authority"] == "UNVERIFIED_PREVIEW_ONLY"
    assert out["preflight_state"] in {"BLOCKED", "UNKNOWN"}
    assert '"PASS"' not in json.dumps(out)
    assert '"READY"' not in json.dumps(out)


def test_single_bot_baseline_unknown_and_links():
    out = offline_role_preflight(single())
    always_nonexecuting(out)
    assert out["preflight_state"] == "UNKNOWN"
    assert len(out["role_graph"]["nodes"]) == 2
    assert out["feature_link"] == {
        "feature_id": "synthetic_feature",
        "kind": "FEATURE_CATALOG_REFERENCE_ONLY",
    }
    assert out["scenario_link"]["scenario_id"] == "synthetic_solo_case"
    assert states(out)["pool_capacity"] == "UNKNOWN"
    assert states(out)["oracle:synthetic_state_oracle"] == "UNKNOWN"
    assert out["checkpoints"][0]["assertion_verdict"] == "UNKNOWN"


def test_three_distinct_roles_checkpoint_dag_and_needs():
    out = offline_role_preflight(triple())
    always_nonexecuting(out)
    assert out["preflight_state"] == "UNKNOWN"
    assert len(out["role_needs"]) == 3
    assert sum(x["lease_units_requested"] for x in out["role_needs"]) == 3
    assert set((e["from"], e["to"], e["kind"]) for e in
               out["role_graph"]["edges"]) >= {
        ("healer_one", "party_checkpoint", "REQUIRED_ROLE"),
        ("dps_one", "party_checkpoint", "REQUIRED_ROLE"),
        ("first_observation", "party_checkpoint", "CHECKPOINT_DEPENDENCY"),
    }
    assert all(c["assertion_verdict"] == "UNKNOWN" for c in out["checkpoints"])


def test_reported_all_covered_still_unknown_not_authorized():
    out = offline_role_preflight(triple(), fully_reported())
    always_nonexecuting(out)
    assert out["preflight_state"] == "UNKNOWN"
    assert states(out)["pool_capacity"] == "DECLARED"
    assert states(out)["lease_ownership"] == "DECLARED"
    assert states(out)["cleanup"] == "DECLARED"
    assert states(out)["oracle:synthetic_party_oracle"] == "DECLARED"
    assert all(not c["source_authenticated"] for c in out["checkpoints"])


def test_missing_healer_blocks_and_remains_nonexecuting():
    claims = fully_reported()
    claims["available_role_kinds"] = ["leader", "dps"]
    out = offline_role_preflight(triple(), claims)
    always_nonexecuting(out)
    assert out["preflight_state"] == "BLOCKED"
    assert "role_coverage" in out["blockers"]
    assert "healer" in states(out).get("role_coverage", "") or (
        "healer" in next(c["detail"] for c in out["checks"]
                         if c["id"] == "role_coverage")
    )


@pytest.mark.parametrize("slots", [0, 1, 2])
def test_insufficient_pool_blocks(slots):
    claims = fully_reported()
    claims["available_pool_slots"] = slots
    out = offline_role_preflight(triple(), claims)
    always_nonexecuting(out)
    assert states(out)["pool_capacity"] == "BLOCKED"
    assert out["preflight_state"] == "BLOCKED"


def test_missing_capability_or_oracle_blocks_without_assertion_pass():
    claims = fully_reported()
    claims["observed_capabilities"] = ["observe_state"]
    claims["oracle_statuses"]["synthetic_party_oracle"] = "MISSING"
    out = offline_role_preflight(triple(), claims)
    always_nonexecuting(out)
    assert states(out)["capability_coverage"] == "BLOCKED"
    assert states(out)["oracle:synthetic_party_oracle"] == "BLOCKED"
    assert "oracle:synthetic_party_oracle" in out["blockers"]


def test_unknown_oracle_and_lease_cleanup_are_unknown():
    claims = fully_reported()
    claims["lease_status"] = "UNKNOWN"
    claims["cleanup_status"] = "UNKNOWN"
    claims["oracle_statuses"]["synthetic_party_oracle"] = "UNKNOWN"
    out = offline_role_preflight(triple(), claims)
    always_nonexecuting(out)
    assert states(out)["lease_ownership"] == "UNKNOWN"
    assert states(out)["cleanup"] == "UNKNOWN"
    assert states(out)["oracle:synthetic_party_oracle"] == "UNKNOWN"
    assert out["preflight_state"] == "UNKNOWN"


@pytest.mark.parametrize("case", [
    {"lease_status": "REPORTED_UNAVAILABLE"},
    {"cleanup_status": "REPORTED_INCOMPLETE"},
])
def test_claimed_unavailable_or_incomplete_blocks(case):
    claims = fully_reported()
    claims.update(case)
    out = offline_role_preflight(triple(), claims)
    always_nonexecuting(out)
    assert out["preflight_state"] == "BLOCKED"


@pytest.mark.parametrize("change", [
    lambda m: m.update({"schema": "xi-test-execution/1"}),
    lambda m: m.update({"schema": "toolkit-r4-synthetic-role-preflight/2"}),
    lambda m: m.update({"execution_enabled": True}),
    lambda m: m["roles"][0].update({"runner": "launch"}),
    lambda m: m["roles"][0].update({"kind": "REAL_ADMIN"}),
    lambda m: m["roles"].append(deepcopy(m["roles"][0])),
    lambda m: m.update({"required_role_kinds": ["leader", "healer"]}),
    lambda m: m["checkpoints"][0].update({"oracle_id": None}),
    lambda m: m["checkpoints"][0].update({"required_role_ids": ["missing_role"]}),
    lambda m: m["checkpoints"][0].update({"depends_on": ["first_observation"]}),
    lambda m: m["checkpoints"][0].update({"depends_on": ["unknown_cp"]}),
    lambda m: m["roles"][0].update({"required_capabilities": ["x", "x"]}),
    lambda m: m["checkpoints"][0].update({"id": "leader_one"}),
    lambda m: m["roles"][0].update({"id": "leader_one/../../"}),
])
def test_unsupported_or_inconsistent_schema_is_blocked(change):
    model = single()
    change(model)
    out = offline_role_preflight(model)
    always_nonexecuting(out)
    assert out["preflight_state"] == "BLOCKED"
    assert "offline_schema" in out["blockers"]


def test_cyclic_checkpoint_graph_fails_closed():
    model = triple()
    model["checkpoints"][0]["depends_on"] = ["party_checkpoint"]
    out = offline_role_preflight(model)
    always_nonexecuting(out)
    assert states(out)["offline_schema"] == "BLOCKED"


@pytest.mark.parametrize("invalid", [
    {"available_pool_slots": True},
    {"available_pool_slots": 2.0},
    {"available_pool_slots": -1},
    {"available_role_kinds": ["healer", "healer"]},
    {"available_role_kinds": ["admin"]},
    {"observed_capabilities": "observe_state"},
    {"lease_status": "VERIFIED"},
    {"cleanup_status": "COMPLETE"},
    {"oracle_statuses": {"fake_oracle": "REPORTED_COVERED"}},
    {"oracle_statuses": {"synthetic_state_oracle": "VERIFIED_PASS"}},
    {"launch": True},
])
def test_unsupported_claim_shapes_block_instead_of_authorize(invalid):
    out = offline_role_preflight(single(), invalid)
    always_nonexecuting(out)
    assert out["preflight_state"] == "BLOCKED"
    assert "offline_schema" in out["blockers"]


def test_definitions_and_claims_are_not_mutated_and_projections_deterministic():
    original = triple()
    claims = fully_reported()
    model_copy, claims_copy = deepcopy(original), deepcopy(claims)
    first = offline_role_preflight(original, claims)
    second = offline_role_preflight(original, claims)
    assert first == second
    assert original == model_copy and claims == claims_copy
    assert len(first["local_definition_sha256"]) == 64


def test_forged_result_field_and_non_json_payload_block():
    original = triple()
    original["authoritative_gameplay_verdict"] = "PASS"
    out = offline_role_preflight(original, fully_reported())
    always_nonexecuting(out)
    assert "offline_schema" in out["blockers"]
    broken = single()
    broken["roles"][0]["required_capabilities"] = [{"bad": {1, 2}}]
    out = offline_role_preflight(broken)
    always_nonexecuting(out)
    assert "offline_schema" in out["blockers"]


def test_oversized_model_and_synthetic_case_has_no_side_effects(tmp_path):
    data = single()
    data["roles"][0]["required_capabilities"] = ["cap_" + "x" * 35000]
    out = offline_role_preflight(data)
    always_nonexecuting(out)
    assert "offline_schema" in out["blockers"]
    assert list(tmp_path.iterdir()) == []
