"""Synthetic-only contract tests for a read-only Headless personality consumer."""
import copy
import hashlib
import json

import pytest

from workbench.personality_catalog_consumer import (
    CatalogPin, CANDIDATE_PIN, CANDIDATE_SOURCE_GIT_BLOB,
    ReadOnlyCatalog, compare_profiles, list_job_profiles,
    load_pinned_manifest,
)

JOBS = (
    "WAR", "MNK", "WHM", "BLM", "RDM", "THF", "PLD", "DRK",
    "BST", "BRD", "RNG", "SAM", "NIN", "DRG", "SMN", "BLU",
    "COR", "PUP", "DNC", "SCH", "GEO", "RUN",
)


def fake_catalog():
    profiles = []
    for i in range(15):
        profiles.append({
            "id": f"fake_profile_{i:02d}",
            "runtime_status": "DESIGN_ONLY",
            "unknown_policy": "INHIBIT_AND_REPORT",
            "action_authority": "EXISTING_HEADLESS_ROUTINES_ONLY",
            "axis": "recovery" if i < 5 else "defense",
            "role_affinity": ["healer"] if i < 5 else ["dps"],
            "behavior_preferences": [
                {"rule_id": f"rule_{i:02d}", "priority": 100,
                 "target_selector": "self", "condition_id": "health_low",
                 "requires_facts": ["own_hp"], "action_intent": "SYMBOLIC_INTENT"}
            ],
        })
    return {
        "schema_version": "1.0.0",
        "catalog_id": "xiheadless-personalities",
        "authority": "XIHEADLESS_CANONICAL_DATA",
        "runtime_status": "DESIGN_ONLY",
        "consumers": {
            "primary": ["xiheadless", "mission_toolkit"],
            "secondary": ["valhalla_trust_adapter"],
        },
        "source_revisions": {"headless_main": "e" * 40, "lsb": "a" * 40},
        "invariants": {
            "no_execution": True,
            "profile_unknown_policy": "INHIBIT_AND_REPORT",
            "action_dispatch": "OUTSIDE_CATALOG_REQUIRES_EXISTING_ROUTINES_AND_ACCEPTED_EVIDENCE",
            "trust_adapter_target_restrictions": "NOT_INHERITED",
        },
        "capabilities": [{"id": "own_hp", "evidence_status": "REQUIRES_ACCEPTANCE"}],
        "jobs": [
            {"job_code": code, "primary_party_role": "dps",
             "eligible_party_roles": ["dps"], "suggested_profile_ids": ["fake_profile_06"],
             "personality_assignment_status": "DESIGN_OPTION_ONLY",
             "headless_job_runtime_status": "NOT_TESTED"}
            for code in JOBS
        ],
        "profiles": profiles,
        "trust_inspirations": [
            {"id": f"lsb_fake_{i:02d}",
             "source_completeness": "sparse_stub" if i == 0 else "declared_rules",
             "profile_inspirations": [] if i == 0 else ["fake_profile_06"],
             "evidence_type": "SOURCE_DECLARATION_ONLY",
             "runtime_status": "NOT_TESTED"}
            for i in range(19)
        ],
    }


def raw_and_pin(catalog=None):
    data = fake_catalog() if catalog is None else catalog
    raw = (json.dumps(data, sort_keys=True) + "\n").encode("utf-8")
    git_sha = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()
    return raw, CatalogPin("sarthax/xiheadless-dsp", "1" * 40, git_sha)


def test_candidate_source_pin_is_real_headless_blob_shape():
    assert len(CANDIDATE_SOURCE_GIT_BLOB) == 40
    assert CANDIDATE_PIN.repository == "sarthax/xiheadless-dsp"


def test_imports_schema_valid_synthetic_review_pin():
    raw, pin = raw_and_pin()
    catalog = load_pinned_manifest(raw, pin)
    assert isinstance(catalog, ReadOnlyCatalog)
    assert catalog.metadata["view_kind"] == "READ_ONLY_PERSONALITY_CATALOG"
    assert catalog.metadata["execution_enabled"] is False
    assert catalog.metadata["gameplay_verdict"] == "NOT_TESTED"
    assert len(catalog.jobs) == 22


def test_default_candidate_pin_rejects_unreviewed_fake_bytes():
    raw, _ = raw_and_pin()
    with pytest.raises(ValueError, match="bytes"):
        load_pinned_manifest(raw)


def test_bytes_fingerprint_mismatch_rejected_even_valid_json():
    raw, pin = raw_and_pin()
    changed = raw.replace(b"fake_profile_06", b"fake_profile_07")
    with pytest.raises(ValueError, match="bytes"):
        load_pinned_manifest(changed, pin)


@pytest.mark.parametrize("repo,sha", [
    ("private-valhalla", "1" * 40),
    ("sarthax/FFXI-Mission-Toolkit", "1" * 40),
    ("sarthax/xiheadless-dsp", "BAD_SHA"),
])
def test_wrong_source_repository_or_commit_fails(repo, sha):
    raw, pin = raw_and_pin()
    with pytest.raises(ValueError):
        load_pinned_manifest(raw, CatalogPin(repo, sha, pin.git_blob_sha1))


@pytest.mark.parametrize("change", [
    lambda d: d.update({"schema_version": "2.0"}),
    lambda d: d.update({"catalog_id": "other"}),
    lambda d: d.update({"authority": "Valhalla"}),
    lambda d: d.update({"runtime_status": "READY"}),
    lambda d: d["consumers"].update({"primary": ["valhalla_trust_adapter"]}),
    lambda d: d["invariants"].update({"no_execution": False}),
    lambda d: d["invariants"].update({"trust_adapter_target_restrictions": "OWNER_ONLY"}),
])
def test_incompatible_schema_or_execution_claim_rejected(change):
    c = fake_catalog()
    change(c)
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError):
        load_pinned_manifest(raw, pin)


def test_job_binding_cannot_claim_runtime_success():
    c = fake_catalog()
    c["jobs"][0]["headless_job_runtime_status"] = "PASSED"
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError, match="job binding"):
        load_pinned_manifest(raw, pin)


def test_profile_cannot_gain_runtime_action_authority():
    c = fake_catalog()
    c["profiles"][0]["action_authority"] = "DIRECT_PLUGIN_SEND"
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError, match="profile"):
        load_pinned_manifest(raw, pin)


def test_missing_or_unsafe_capability_observation_rejected():
    c = fake_catalog()
    c["capabilities"][0]["evidence_status"] = "LIVE_CONFIRMED"
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError, match="source presence"):
        load_pinned_manifest(raw, pin)


def test_unreviewed_lsb_stub_not_assigned_traits():
    c = fake_catalog()
    c["trust_inspirations"][0]["profile_inspirations"] = ["fake_profile_06"]
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError, match="sparse"):
        load_pinned_manifest(raw, pin)


def test_unknown_profile_reference_rejected():
    c = fake_catalog()
    c["jobs"][0]["suggested_profile_ids"].append("no_such_profile")
    raw, pin = raw_and_pin(c)
    with pytest.raises(ValueError, match="profile"):
        load_pinned_manifest(raw, pin)


def test_duplicate_profile_and_job_rejected():
    for key in ("profiles", "jobs"):
        c = fake_catalog()
        c[key][1] = copy.deepcopy(c[key][0])
        raw, pin = raw_and_pin(c)
        with pytest.raises(ValueError):
            load_pinned_manifest(raw, pin)


def test_preview_comparison_only_displays_intent_and_requirements():
    raw, pin = raw_and_pin()
    catalog = load_pinned_manifest(raw, pin)
    result = compare_profiles(catalog, ["fake_profile_01", "fake_profile_08"])
    assert result["execution_enabled"] is False
    assert result["gameplay_verdict"] == "NOT_TESTED"
    assert result["view_kind"] == "READ_ONLY_COMPARISON"
    assert result["profiles"][0]["required_fact_ids"] == ["own_hp"]
    assert result["profiles"][0]["intent_rules"][0]["action_intent"] == "SYMBOLIC_INTENT"
    assert "dispatch" not in json.dumps(result).lower()


def test_job_preview_is_design_only():
    raw, pin = raw_and_pin()
    data = list_job_profiles(load_pinned_manifest(raw, pin), "COR")
    assert data["job_code"] == "COR"
    assert data["assignment_status"] == "DESIGN_OPTION_ONLY"
    assert data["execution_enabled"] is False


@pytest.mark.parametrize("profiles", [
    [],
    ["fake_profile_01", "fake_profile_01"],
    ["missing"],
    [f"fake_profile_{n:02d}" for n in range(7)],
])
def test_bad_compare_request_fails(profiles):
    raw, pin = raw_and_pin()
    catalog = load_pinned_manifest(raw, pin)
    with pytest.raises(ValueError):
        compare_profiles(catalog, profiles)


def test_unknown_job_is_not_implicitly_mapped():
    raw, pin = raw_and_pin()
    catalog = load_pinned_manifest(raw, pin)
    with pytest.raises(ValueError, match="unknown"):
        list_job_profiles(catalog, "TRUST")


def test_original_source_is_unmodified_by_readonly_view():
    c = fake_catalog()
    raw, pin = raw_and_pin(c)
    before = copy.deepcopy(c)
    data = load_pinned_manifest(raw, pin)
    compare_profiles(data, ["fake_profile_08"])
    list_job_profiles(data, "COR")
    assert c == before
