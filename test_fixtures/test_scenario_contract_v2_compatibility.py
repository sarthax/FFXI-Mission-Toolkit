"""SYNTHETIC, offline compatibility gates for #1259; no DSP/client/runtime IO."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.assertion_engine import evaluate
from workbench.server_admin.feature_testing.scenario_contract_v2 import (
    base_spec_sha256, compatibility_report, deserialize_spec, serialize_spec,
)
from workbench.server_admin.feature_testing.scenario_presentation import scenario_presentation
from workbench.server_admin.feature_testing.test_specifications import (
    specification, specifications, validate_spec,
)

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "test_fixtures" / "scenario_contract_v2_gardening_migration_synthetic.json"
PIN = "330ea8f854cff47aae570aa95d6474f3225f5d49"


def staged_fixture():
    envelope = json.loads(CASE.read_text(encoding="utf-8"))
    assert envelope["_fixture_note"].startswith("SYNTHETIC NON-CANONICAL")
    return envelope


def _fingerprint_ready():
    """Invented SYNTHETIC bytes, NOT actual DSP file content or server state."""
    spec = deepcopy(staged_fixture()["specification"])
    spec["contract_v2"]["sources"][0]["sha256"] = hashlib.sha256(
        b"SYNTHETIC fixture source bytes (not real garden SQL)"
    ).hexdigest()
    spec["contract_v2"]["fingerprints"].update({
        "base_spec_sha256": base_spec_sha256(spec),
        "dsp_commit": "a" * 40,
        "headless_commit": "b" * 40,
        "toolkit_commit": "c" * 40,
    })
    source = spec["contract_v2"]["sources"][0]
    observed_versions = {
        "dsp_commit": "a" * 40,
        "headless_commit": "b" * 40,
        "toolkit_commit": "c" * 40,
    }
    observed_sources = {
        source["ref"]: {"revision": PIN, "sha256": source["sha256"]}
    }
    return spec, observed_versions, observed_sources


def test_canonical_v1_examples_unchanged_under_latest_validator_and_viewer():
    actual = {(x["feature_id"], x["case_id"]): x for x in specifications()}
    assert ("moghancement", "MOG-09") in actual
    assert ("inventory_observation", "INV-OBS-01") in actual
    for name in (("moghancement", "MOG-09"), ("inventory_observation", "INV-OBS-01")):
        original = deepcopy(specification(*name))
        baseline = scenario_presentation(original)
        assert validate_spec(original) == actual[name]
        assert deserialize_spec(serialize_spec(original)) == original
        assert scenario_presentation(original) == baseline
        assert "contract_v2" not in original
        assert compatibility_report(original)["state"] == "UNKNOWN"
        assert compatibility_report(original)["independent_verification"] == "NOT_ESTABLISHED"
        assert compatibility_report(original)["execution_enabled"] is False
    assert actual["moghancement", "MOG-09"]["runner"] == "xiheadless_observation_v1"
    assert actual["inventory_observation", "INV-OBS-01"]["runner"] == "unassigned"


def test_source_backed_staged_gardening_citation_not_promoted_to_executable_spec():
    envelope = staged_fixture()
    assert envelope["staged_origin"]["feature_id"] == "gardening"
    assert envelope["staged_origin"]["case_id"] == "GARD-01"
    assert envelope["staged_origin"]["import_status"].startswith("BLOCKED")
    spec = envelope["specification"]
    src = spec["contract_v2"]["sources"][0]
    assert (src["repository"], src["path"], src["line_start"], src["line_end"]) == (
        "sarthax/darkstar-to-valhalla", "sql/char_inventory.sql", 19, 29)
    assert src["revision"] == PIN and src["sha256"] is None
    assert spec["schema_version"] == 1
    assert spec["execution_status"] == "design_only" and spec["runner"] == "unassigned"
    assert spec["contract_v2"]["parameters"][0]["binding_state"] == "unresolved"
    assert spec["contract_v2"]["oracles"][0]["oracle_type"] == "unknown"
    assert spec["contract_v2"]["step_requirements"][0]["execution_gate"] == "blocked"
    assert spec["assertions"][0]["expected"] is None
    validate_spec(spec)
    assert deserialize_spec(serialize_spec(spec)) == spec
    assert evaluate(spec, {"session": "SYNTHETIC placeholder"})["verdict"] == "BLOCKED"
    view = scenario_presentation(spec)
    assert view["independent_verification"] == "NOT_ESTABLISHED"
    assert view["recorded_verdict"] is None and view["recalculated_verdict"] is None
    assert compatibility_report(spec)["state"] == "UNKNOWN"
    assert any("unpinned" in r for r in compatibility_report(spec)["reasons"])


def test_staging_examples_remain_outside_canonical_catalog():
    assert specification("gardening", "SYNTH-GARD-01-V2-MIGRATION") is None
    assert specification("gardening", "GARD-01") is None


def test_missing_source_bytes_stay_unknown_even_with_engine_pins():
    spec, versions, sources = _fingerprint_ready()
    assert compatibility_report(spec, versions)["state"] == "UNKNOWN"
    assert any("rehashed" in s for s in compatibility_report(spec, versions)["reasons"])
    assert compatibility_report(spec, versions, observed_sources={})["state"] == "UNKNOWN"
    assert any("not supplied" in s for s in compatibility_report(
        spec, versions, observed_sources={})["reasons"])


def test_missing_cited_digest_stays_unknown_even_with_claimed_rehash():
    spec, versions, sources = _fingerprint_ready()
    spec["contract_v2"]["sources"][0]["sha256"] = None
    spec["contract_v2"]["fingerprints"]["base_spec_sha256"] = base_spec_sha256(spec)
    check = compatibility_report(spec, versions, observed_sources=sources)
    assert check["state"] == "UNKNOWN"
    assert any("unpinned" in why for why in check["reasons"])
    assert check["independent_verification"] == "NOT_ESTABLISHED"


def test_source_revision_or_content_hash_mismatch_is_blocked():
    spec, versions, sources = _fingerprint_ready()
    diff_hash = deepcopy(sources)
    diff_hash["garden-pot-extra"]["sha256"] = "f" * 64
    check = compatibility_report(spec, versions, observed_sources=diff_hash)
    assert check["state"] == "BLOCKED"
    assert any("content SHA-256 mismatch" in why for why in check["reasons"])
    diff_revision = deepcopy(sources)
    diff_revision["garden-pot-extra"]["revision"] = "f" * 40
    check = compatibility_report(spec, versions, observed_sources=diff_revision)
    assert check["state"] == "BLOCKED"
    assert any("revision mismatch" in why for why in check["reasons"])


def test_engine_or_base_spec_mismatch_blocks_even_when_sources_match():
    spec, versions, sources = _fingerprint_ready()
    bad = dict(versions, dsp_commit="f" * 40)
    assert compatibility_report(spec, bad, observed_sources=sources)["state"] == "BLOCKED"
    spec["preconditions"].append("Synthetic change invalidates old spec hash")
    assert compatibility_report(spec, versions, observed_sources=sources)["state"] == "BLOCKED"


def test_all_structural_fingerprints_matching_never_authorize_execution():
    spec, versions, sources = _fingerprint_ready()
    report = compatibility_report(spec, versions, observed_sources=sources)
    assert report["state"] == "MATCHED_PINNED_ONLY"
    assert report["execution_enabled"] is False
    assert report["independent_verification"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("broken", [
    {"garden-pot-extra": {"revision": "not-sha", "sha256": "a" * 64}},
    {"garden-pot-extra": {"revision": PIN, "sha256": "bad"}},
    {"garden-pot-extra": {"revision": PIN, "sha256": "a" * 64, "approved": True}},
    {"unrecognized-ref": {"revision": PIN, "sha256": "a" * 64}},
    ["invalid-map"],
    {"garden-pot-extra": {"revision": True, "sha256": "a" * 64}},
])
def test_malformed_or_forged_source_fingerprint_evidence_is_rejected(broken):
    spec, versions, _ = _fingerprint_ready()
    with pytest.raises(ValueError):
        compatibility_report(spec, versions, observed_sources=broken)


def test_unverified_metadata_permissions_are_never_runner_approvals():
    spec = deepcopy(staged_fixture()["specification"])
    req = spec["contract_v2"]["step_requirements"][0]
    req["required_permissions"] = ["server_read_grant", "database_write"]
    with pytest.raises(ValueError, match="permission"):
        validate_spec(spec)
    req["required_permissions"] = ["server_read_grant"]
    req["execution_gate"] = "ready"
    with pytest.raises(ValueError, match="authorize execution"):
        validate_spec(spec)
    req["execution_gate"] = "blocked"
    req["capability"] = "sql_execute"
    with pytest.raises(ValueError, match="capability"):
        validate_spec(spec)


def test_unknown_oracle_stays_unknown_with_non_normative_diagnostics():
    spec = deepcopy(staged_fixture()["specification"])
    assert spec["contract_v2"]["oracles"][0]["source_refs"] == []
    oracle = spec["contract_v2"]["oracles"][0]
    oracle["confidence"] = "source_cited"
    with pytest.raises(ValueError, match="unknown v2 oracle"):
        validate_spec(spec)
    oracle["confidence"] = "unknown"
    oracle["source_refs"] = ["garden-pot-extra"]
    with pytest.raises(ValueError, match="unknown v2 oracle"):
        validate_spec(spec)


def test_unverified_binding_cannot_be_promoted_by_source_citation_alone():
    spec = deepcopy(staged_fixture()["specification"])
    p = spec["contract_v2"]["parameters"][0]
    p.update(binding_state="independently_source_verified", identity=42, namespace="synthetic_catalog")
    # Pinned commit alone is insufficient; content digest is UNKNOWN.
    with pytest.raises(ValueError, match="pinned"):
        validate_spec(spec)
    p.update(binding_state="ambiguous", identity=None, namespace=None)
    assert validate_spec(spec) == spec


def test_stale_fingerprint_on_editor_clone_must_not_be_silent_match():
    spec, versions, sources = _fingerprint_ready()
    spec["case_id"] = "SYNTH-GARD-01-COPIED"
    assert compatibility_report(spec, versions, observed_sources=sources)["state"] == "BLOCKED"


def test_guided_editor_preserves_optional_v2_without_approving_binding_or_oracle():
    """Canonical validation may preserve metadata; it is not source trust."""
    from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec

    mog = deepcopy(specification("moghancement", "MOG-09"))
    mog.update(case_id="SYNTH-MOG-V2-PREVIEW", runner="unassigned",
               execution_status="design_only")
    mog["authoring"] = {
        "state": "draft",
        "execution_policy": "read_only",
        "evidence_provenance": "synthetic_untrusted",
        "blocking_gaps": ["UNKNOWN source and independent readback"],
        "review_required": True,
    }
    mog["contract_v2"] = {
        "contract_version": 2,
        "sources": [{
            "ref": "synthetic-src", "repository": "synthetic/repository",
            "path": "synthetic/source.lua", "line_start": 1, "line_end": 3,
            "revision": None, "sha256": None, "classification": "dsp_source",
        }],
        "parameters": [{
            "name": "synthetic_npc", "kind": "npc", "identity": None,
            "namespace": None, "zone_id": None, "binding_state": "ambiguous",
            "source_refs": ["synthetic-src"],
        }],
        "oracles": [{
            "assertion_id": mog["assertions"][0]["id"], "oracle_type": "unknown",
            "confidence": "unknown", "source_refs": [],
        }],
        "step_requirements": [{
            "step_id": mog["steps"][0]["id"],
            "capability": "read_only_observation", "operation_class": "read_only",
            "required_permissions": [], "required_readbacks": ["session"],
            "approval_required": True, "execution_gate": "blocked",
        }],
        "fingerprints": {
            "base_spec_sha256": None, "dsp_commit": None,
            "headless_commit": None, "toolkit_commit": None,
        },
    }
    original = deepcopy(mog)
    result = validate_editor_spec(mog)
    assert result["canonical_specification"]["contract_v2"] == original["contract_v2"]
    assert result["execution_enabled"] is False
    assert result["preview"]["independent_verification"] == "NOT_ESTABLISHED"
    assert result["preview"]["recorded_verdict"] is None
    assert deserialize_spec(serialize_spec(result["canonical_specification"])) == original
    # No source rehash or trusted runtime fingerprint is invented.
    assert compatibility_report(original)["state"] == "UNKNOWN"
    assert all(req["execution_gate"] == "blocked"
               for req in result["canonical_specification"]["contract_v2"]["step_requirements"])


def test_v2_metadata_cannot_bypass_existing_32k_draft_serialization_limit():
    spec = deepcopy(staged_fixture()["specification"])
    base = deepcopy(spec["steps"][0])
    # 100 steps and 500-character source-neutral titles/expectations fit
    # individual v1 schema caps but exceed the existing 32 KiB draft size.
    spec["steps"] = [
        {**deepcopy(base), "id": f"SYNTH-LARGE-{i}",
         "title": "SYNTHETIC-" + "t" * 480,
         "expected": "UNKNOWN " + "x" * 480}
        for i in range(100)
    ]
    # No authored step requires execution; keep its one existing blocked gate.
    spec["contract_v2"]["step_requirements"][0]["step_id"] = "SYNTH-LARGE-0"
    assert validate_spec(spec) is spec
    with pytest.raises(ValueError, match="32KiB"):
        serialize_spec(spec)
    assert spec["runner"] == "unassigned"


def test_unicode_draft_size_must_match_current_ascii_escaped_sqlite_storage():
    spec = deepcopy(staged_fixture()["specification"])
    base = deepcopy(spec["steps"][0])
    spec["steps"] = [
        {**deepcopy(base), "id": f"SYNTH-UNICODE-{n}",
         "title": "Synthetic Unicode source-neutral step",
         "expected": "UNKNOWN " + "雪" * 450}
        for n in range(16)
    ]
    spec["contract_v2"]["step_requirements"][0]["step_id"] = "SYNTH-UNICODE-0"
    assert validate_spec(spec) is spec
    utf8_json = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    existing_store_json = json.dumps(spec, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    assert len(utf8_json.encode("utf-8")) < 32768
    assert len(existing_store_json.encode("utf-8")) > 32768
    with pytest.raises(ValueError, match="32KiB"):
        serialize_spec(spec)
    with pytest.raises(ValueError, match="32KiB"):
        deserialize_spec(utf8_json)


def test_actual_sqlite_storage_bytes_match_v2_contract_and_unicode_limit(monkeypatch, tmp_path):
    """Check exact SQLite content bytes, not only an estimated serializer."""
    import sqlite3
    from workbench.server_admin.feature_testing.spec_drafts import save_draft

    db = tmp_path / "canonical_v2_actual_bytes.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(db))
    small = deepcopy(staged_fixture()["specification"])
    small["purpose"] = "SYNTHETIC 雪 provenance with UNKNOWN oracle"
    expected_wire = json.dumps(small, sort_keys=True, separators=(",", ":"))
    assert len(expected_wire.encode("utf-8")) < 32768
    assert save_draft(small, 0)["revision"] == 1
    with sqlite3.connect(str(db)) as conn:
        row = conn.execute(
            "SELECT CAST(content AS BLOB), revision FROM test_spec_drafts WHERE case_id=?",
            (small["case_id"],)
        ).fetchone()
    assert row[1] == 1
    assert row[0] == expected_wire.encode("utf-8")
    assert deserialize_spec(serialize_spec(small)) == small

    large = deepcopy(staged_fixture()["specification"])
    base = deepcopy(large["steps"][0])
    large["steps"] = [
        {**deepcopy(base), "id": f"SYNTH-SQLITE-UNICODE-{i}",
         "title": "SYNTHETIC Unicode storage check",
         "expected": "UNKNOWN " + "雪" * 450}
        for i in range(16)
    ]
    large["contract_v2"]["step_requirements"][0]["step_id"] = "SYNTH-SQLITE-UNICODE-0"
    assert validate_spec(large) is large
    assert len(json.dumps(large, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) < 32768
    assert len(json.dumps(large, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 32768
    with pytest.raises(ValueError, match="32KiB"):
        save_draft(large, 0)
    with pytest.raises(ValueError, match="32KiB"):
        serialize_spec(large)
    with sqlite3.connect(str(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM test_spec_drafts").fetchone()[0] == 1
