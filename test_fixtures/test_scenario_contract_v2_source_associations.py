"""R7 read-only source attribution: explicit scope, UNKNOWN by default.

All tests synthetic/offline. No live source rehash, DSP, client or execution.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.scenario_contract_v2 import (
    base_spec_sha256, compatibility_report, deserialize_spec,
    serialize_spec, source_attribution_report,
)
from workbench.server_admin.feature_testing.scenario_contract_v2_adapters import project_domain_case
from workbench.server_admin.feature_testing.test_specifications import (
    specification, validate_spec,
)

ROOT = Path(__file__).resolve().parent
TEST = ROOT / "scenario_contract_v2_synthetic.json"
DOMAINS = {
    "gardening": "GARD-01",
    "voidwalker": "VWK-01",
    "assault_nyzul": "ASLT-01",
    "missions_quests": "MQ-01",
    "moghancement": "MOG-01",
    "voidwatch": "VOID-01",
    "salvage": "SAL-01",
    "run_geo_unlock": "RG-01",
    "chocobo_raising": "CHO-01",
}
STEP = "SYNTH-V2-S01"
REF = "synthetic-source-1"


def spec():
    return deepcopy(json.loads(TEST.read_text(encoding="utf-8"))["specification"])


def associations():
    return [
        {"scope": "case", "target_id": None, "source_refs": [REF]},
        {"scope": "step", "target_id": STEP, "source_refs": [REF]},
    ]


def test_legacy_v1_without_v2_remains_unchanged_and_unattributed():
    for domain, case in (("moghancement", "MOG-09"),
                         ("inventory_observation", "INV-OBS-01")):
        original = deepcopy(specification(domain, case))
        assert "contract_v2" not in original
        assert validate_spec(original) == original
        assert deserialize_spec(serialize_spec(original)) == original
        result = source_attribution_report(original)
        assert result["case"]["state"] == "UNKNOWN"
        assert result["execution_enabled"] is False
        assert result["independent_verification"] == "NOT_ESTABLISHED"


def test_old_v2_metadata_stays_unchanged_unattributed_and_roundtrips():
    original = spec()
    assert "source_associations" not in original["contract_v2"]
    assert validate_spec(original) == original
    assert deserialize_spec(serialize_spec(original)) == original
    result = source_attribution_report(original)
    assert result["case"] == {"state": "UNKNOWN", "source_refs": []}
    assert result["steps"][STEP]["state"] == "UNKNOWN"
    assert result["steps"][STEP]["source_refs"] == []
    assert result["oracle_approval"] == "NOT_ESTABLISHED"


def test_explicit_case_and_step_attribution_survive_serialization():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    before_core = base_spec_sha256(original)
    assert validate_spec(original) == original
    encoded = serialize_spec(original)
    restored = deserialize_spec(encoded)
    assert restored == original
    assert restored["contract_v2"]["source_associations"] == associations()
    assert base_spec_sha256(restored) == before_core
    result = source_attribution_report(restored)
    assert result["case"] == {
        "state": "EXPLICIT_CITATION_CLAIM", "source_refs": [REF]}
    assert result["steps"][STEP] == {
        "state": "EXPLICIT_CITATION_CLAIM", "source_refs": [REF]}
    assert result["execution_enabled"] is False
    assert result["independent_verification"] == "NOT_ESTABLISHED"
    assert compatibility_report(restored)["state"] == "UNKNOWN"


def test_case_attribution_does_not_imply_step_attribution():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()[:1]
    assert validate_spec(original) == original
    result = source_attribution_report(original)
    assert result["case"]["state"] == "EXPLICIT_CITATION_CLAIM"
    assert result["steps"][STEP] == {"state": "UNKNOWN", "source_refs": []}


def test_step_attribution_does_not_imply_case_attribution():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()[1:]
    assert validate_spec(original) == original
    result = source_attribution_report(original)
    assert result["case"]["state"] == "UNKNOWN"
    assert result["steps"][STEP]["state"] == "EXPLICIT_CITATION_CLAIM"


def test_parameter_and_oracle_sources_do_not_imply_step_attribution():
    original = spec()
    oracle = original["contract_v2"]["oracles"][0]
    oracle.update(oracle_type="source_rule", confidence="candidate",
                  source_refs=[REF])
    # A source-backed expected *candidate* remains non-normative and
    # unapproved. Existing parameter is ambiguous and may cite a source.
    assert original["contract_v2"]["parameters"][0]["binding_state"] == "ambiguous"
    assert original["contract_v2"]["parameters"][0]["identity"] is None
    assert validate_spec(original) == original
    after = deserialize_spec(serialize_spec(original))
    assert after["contract_v2"]["oracles"][0] == oracle
    result = source_attribution_report(after)
    assert result["steps"][STEP]["state"] == "UNKNOWN"
    assert result["oracle_approval"] == "NOT_ESTABLISHED"
    assert after["assertions"][0]["expected"] == "UNKNOWN"


@pytest.mark.parametrize("edit", [
    lambda rows: rows[0].update(scope="runtime"),
    lambda rows: rows[0].update(target_id=STEP),
    lambda rows: rows[1].update(target_id=None),
    lambda rows: rows[1].update(target_id="SYNTH-UNKNOWN-STEP"),
    lambda rows: rows[0].update(source_refs=["fabricated-source"]),
    lambda rows: rows[0].update(source_refs=[REF, REF]),
    lambda rows: rows[0].update(source_refs=[]),
    lambda rows: rows[1].update(execution_gate="ready"),
    lambda rows: rows[1].update(source_refs=[123]),
    lambda rows: rows.append(deepcopy(rows[1])),
    lambda rows: rows.append(deepcopy(rows[0])),
])
def test_broken_ambiguous_or_authorizing_associations_are_rejected(edit):
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    edit(original["contract_v2"]["source_associations"])
    with pytest.raises(ValueError):
        validate_spec(original)


@pytest.mark.parametrize("bad", [None, {}, "step", [{"scope": "case"}]])
def test_malformed_optional_association_container_is_rejected(bad):
    original = spec()
    original["contract_v2"]["source_associations"] = bad
    with pytest.raises(ValueError):
        validate_spec(original)


def test_conflicting_revisions_for_same_path_at_one_target_are_rejected():
    original = spec()
    source = original["contract_v2"]["sources"][0]
    source["revision"] = "a" * 40
    source2 = deepcopy(source)
    source2.update(ref="synthetic-source-2", revision="b" * 40)
    original["contract_v2"]["sources"].append(source2)
    original["contract_v2"]["source_associations"] = [{
        "scope": "step", "target_id": STEP,
        "source_refs": [REF, "synthetic-source-2"],
    }]
    with pytest.raises(ValueError, match="conflicting source revisions"):
        validate_spec(original)


def test_conflicting_digests_for_same_file_at_one_target_are_rejected():
    original = spec()
    source = original["contract_v2"]["sources"][0]
    source.update(revision="a" * 40, sha256="b" * 64)
    source2 = deepcopy(source)
    source2.update(ref="synthetic-source-2", sha256="c" * 64)
    original["contract_v2"]["sources"].append(source2)
    original["contract_v2"]["source_associations"] = [{
        "scope": "step", "target_id": STEP,
        "source_refs": [REF, "synthetic-source-2"],
    }]
    with pytest.raises(ValueError, match="conflicting source revisions or digests"):
        validate_spec(original)


def test_missing_independent_source_fingerprint_is_unknown_and_drift_blocked():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    assert compatibility_report(original)["state"] == "UNKNOWN"
    original["contract_v2"]["fingerprints"]["base_spec_sha256"] = "f" * 64
    assert compatibility_report(original)["state"] == "BLOCKED"
    assert source_attribution_report(original)["steps"][STEP]["state"] == "EXPLICIT_CITATION_CLAIM"


def test_unapproved_oracles_and_mutating_steps_stay_blocked():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    req = original["contract_v2"]["step_requirements"][0]
    assert req["execution_gate"] == "blocked"
    assert original["runner"] == "unassigned"
    assert original["execution_status"] == "design_only"
    req["execution_gate"] = "ready"
    with pytest.raises(ValueError, match="cannot authorize execution"):
        validate_spec(original)


@pytest.mark.parametrize("domain,case_id", list(DOMAINS.items()))
def test_nine_integrated_domain_layouts_remain_noncanonical(domain, case_id):
    staging = json.loads(
        (ROOT.parent / "data" / "testing" / "domain_drafts" /
         (domain + ".json")).read_text(encoding="utf-8")
    )
    view = project_domain_case(staging, case_id)
    assert view["canonical_import_allowed"] is False
    assert view["execution_enabled"] is False
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert view["sources"] and view["source_refs_original"]
    assert view["oracles"] == [] and view["parameters"] == []
    assert all(row["execution_gate"] == "blocked"
               for row in view["step_requirements"])
    assert specification(domain, case_id) is None


def test_unicode_associations_remain_within_existing_storage_size_limits():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    raw = serialize_spec(original)
    assert deserialize_spec(raw) == original
    assert "source_associations" in raw
    assert len(json.dumps(original, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("utf-8")) <= 32768
    # The draft-size rejection is already regression tested by the original
    # SQLite save_draft test; this extension must use the same serialization.


def test_copied_step_attribution_cannot_leak_to_another_case_with_different_step_id():
    """Copied v2 association cannot silently follow a renamed v1 step."""
    parent = spec()
    parent["contract_v2"]["source_associations"] = associations()
    copied = deepcopy(parent)
    copied["case_id"] = "SYNTH-V2-OTHER-CASE"
    copied["steps"][0]["id"] = "OTHER-CASE-S01"
    # The copied association is still bound to SYNTH-V2-S01, not to
    # whichever step happens to occupy the same positional index.
    copied["contract_v2"]["step_requirements"][0]["step_id"] = "OTHER-CASE-S01"
    with pytest.raises(ValueError, match="source association references unknown step"):
        validate_spec(copied)
    copied["contract_v2"]["source_associations"] = associations()[:1]
    assert validate_spec(copied) == copied
    assert source_attribution_report(copied)["steps"]["OTHER-CASE-S01"]["state"] == "UNKNOWN"


def test_copy_with_same_step_id_and_old_case_fingerprint_is_blocked_not_trusted():
    """Exact ID reuse is not independent cross-case provenance attestation."""
    parent = spec()
    parent["contract_v2"]["source_associations"] = associations()
    parent["contract_v2"]["fingerprints"]["base_spec_sha256"] = base_spec_sha256(parent)
    assert validate_spec(parent) == parent
    copied = deepcopy(parent)
    copied["case_id"] = "SYNTH-V2-COPIED-WITH-SAME-STEP-ID"
    assert validate_spec(copied) == copied  # metadata is still descriptive
    report = compatibility_report(copied)
    assert report["state"] == "BLOCKED"
    assert any("base specification SHA-256 mismatch" in reason
               for reason in report["reasons"])
    scoped = source_attribution_report(copied)
    assert scoped["steps"][STEP]["state"] == "EXPLICIT_CITATION_CLAIM"
    assert scoped["independent_verification"] == "NOT_ESTABLISHED"
    assert scoped["execution_enabled"] is False


def test_copy_with_unpinned_fingerprint_has_unknown_not_cross_case_proof():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    cloned = deepcopy(original)
    cloned["case_id"] = "SYNTH-V2-UNPINNED-OTHER-CASE"
    assert validate_spec(cloned) == cloned
    assert compatibility_report(cloned)["state"] == "UNKNOWN"
    assert source_attribution_report(cloned)["independent_verification"] == "NOT_ESTABLISHED"


def test_duplicate_json_association_keys_cannot_override_previous_provenance():
    original = spec()
    original["contract_v2"]["source_associations"] = associations()
    payload = serialize_spec(original)
    assert '"source_associations":[' in payload
    duplicate = payload.replace('"scope":"step"', '"scope":"case","scope":"step"', 1)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        deserialize_spec(duplicate)


def test_integrated_staged_duplicate_citation_url_tampering_fails_before_dedup():
    """Historical #39617090965 bypass stays closed against integrated JSON."""
    document = json.loads(
        (ROOT.parent / "data" / "testing" / "domain_drafts" /
         "run_geo_unlock.json").read_text(encoding="utf-8")
    )
    case = next(item for item in document["cases"] if item["case_id"] == "RG-01")
    assert case["source_refs"][0] == case["steps"][0]["source_refs"][0]
    case["steps"][0]["source_refs"][0]["url"] = "https://example.invalid/forged"
    with pytest.raises(ValueError, match="URL conflicts"):
        project_domain_case(document, "RG-01")


def test_empty_optional_collection_means_unknown_not_verified_or_executable():
    original = spec()
    original["contract_v2"]["source_associations"] = []
    assert deserialize_spec(serialize_spec(original)) == original
    projected = source_attribution_report(original)
    assert projected["case"]["state"] == "UNKNOWN"
    assert projected["steps"][STEP]["state"] == "UNKNOWN"
    assert projected["oracle_approval"] == "NOT_ESTABLISHED"
    assert projected["execution_enabled"] is False


@pytest.mark.parametrize("name,reason", [
    ("invalid_step", "source association references unknown step"),
    ("invalid_source", "unknown, duplicate, or invalid v2 association source reference"),
])
def test_editor_ready_invalid_canonical_json_fixture_is_rejected(name, reason):
    """Direct editor JSON samples intentionally fail canonical validation."""
    doc = json.loads((ROOT / (
        "r7_contract_v2_source_associations_" + name + "_synthetic.json"
    )).read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["runner"] == "unassigned"
    assert doc["execution_status"] == "design_only"
    with pytest.raises(ValueError, match=reason):
        validate_spec(doc)
    with pytest.raises(ValueError):
        serialize_spec(doc)


def test_editor_ready_valid_canonical_json_fixture_round_trips_exactly():
    doc = json.loads((ROOT /
        "r7_contract_v2_source_associations_valid_synthetic.json"
    ).read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["runner"] == "unassigned"
    assert doc["execution_status"] == "design_only"
    assert validate_spec(doc) is doc
    serialized = serialize_spec(doc)
    assert deserialize_spec(serialized) == doc
    presentation = source_attribution_report(doc)
    assert presentation["case"] == {
        "state": "EXPLICIT_CITATION_CLAIM",
        "source_refs": ["synthetic-source-1"],
    }
    assert presentation["steps"][STEP] == {
        "state": "EXPLICIT_CITATION_CLAIM",
        "source_refs": ["synthetic-source-1"],
    }
    assert presentation["execution_enabled"] is False
    assert presentation["oracle_approval"] == "NOT_ESTABLISHED"
    assert presentation["independent_verification"] == "NOT_ESTABLISHED"
    assert compatibility_report(doc)["state"] == "UNKNOWN"
    assert len(json.dumps(doc, sort_keys=True, ensure_ascii=True,
                          separators=(",", ":")).encode("utf-8")) <= 32768
    # Synthetics are not entries in the canonical, runnable test catalog.
    assert specification(doc["feature_id"], doc["case_id"]) is None
