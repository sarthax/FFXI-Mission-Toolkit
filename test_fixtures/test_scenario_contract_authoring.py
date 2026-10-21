"""R7 #1302 canonical optional-v2 Scenario Developer integration.

Synthetic and temporary SQLite only. Never executes, authorizes a runner,
promotes a capture oracle, contacts DSP, or accesses the browser.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_fixtures.test_scenario_guided_editor import synthetic_draft
from workbench.server_admin.feature_testing.scenario_contract_v2 import (
    base_spec_sha256, compatibility_report,
)
from workbench.server_admin.feature_testing.spec_drafts import get_drafts, save_draft
from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec


def with_v2():
    spec = synthetic_draft()
    sid = spec["steps"][0]["id"]
    aid = spec["steps"][0]["assertion_ids"][0]
    spec["contract_v2"] = {
        "contract_version": 2,
        "sources": [{
            "ref": "SourceOne", "repository": "sarthax/darkstar-to-valhalla",
            "path": "scripts/zones/Synthetic_Zone/npcs/Example.lua",
            "line_start": 10, "line_end": 12, "revision": "a" * 40,
            "classification": "dsp_source", "sha256": None,
        }],
        "parameters": [{
            "name": "npc_candidate", "kind": "npc", "identity": None,
            "namespace": None, "zone_id": None, "binding_state": "ambiguous",
            "source_refs": ["SourceOne"],
        }],
        "oracles": [{
            "assertion_id": aid, "oracle_type": "source_rule",
            "source_refs": ["SourceOne"], "confidence": "candidate",
        }],
        "step_requirements": [{
            "step_id": sid, "capability": "server_readback_candidate",
            "operation_class": "read_only", "required_permissions": ["server_read_grant"],
            "required_readbacks": ["client_inventory_readback", "server_inventory_readback"],
            "approval_required": True, "execution_gate": "blocked",
        }],
        "fingerprints": {
            "base_spec_sha256": base_spec_sha256(spec), "dsp_commit": None,
            "headless_commit": None, "toolkit_commit": None,
        }
    }
    return spec


def test_legacy_v1_editor_stays_unmodified():
    spec = synthetic_draft()
    result = validate_editor_spec(spec)
    assert "contract_v2" not in result["canonical_specification"]
    assert result["contract_v2_compatibility"] is None
    assert result["execution_enabled"] is False
    assert all(row["verdict"] == "UNKNOWN" for row in result["preview"]["steps"])


def test_accepted_v2_is_display_only_unknown_without_observed_source_bytes():
    spec = with_v2()
    original = deepcopy(spec)
    result = validate_editor_spec(spec)
    assert result["canonical_specification"] == original
    assert result["contract_v2_compatibility"]["state"] == "UNKNOWN"
    assert result["contract_v2_compatibility"]["execution_enabled"] is False
    assert result["contract_v2_compatibility"]["independent_verification"] == "NOT_ESTABLISHED"
    assert result["preview"]["steps"][0]["verdict"] == "UNKNOWN"
    assert result["reader_view"]["steps"][0]["status"] == "UNKNOWN"
    assert result["operator_review_required"] is True
    assert spec["contract_v2"]["parameters"][0]["identity"] is None
    assert spec["contract_v2"]["oracles"][0]["confidence"] == "candidate"
    assert spec["contract_v2"]["step_requirements"][0]["execution_gate"] == "blocked"


def test_stale_base_spec_fingerprint_is_blocked_but_not_recomputed():
    spec = with_v2()
    pinned = spec["contract_v2"]["fingerprints"]["base_spec_sha256"]
    spec["name"] = "New core content requires manual repinning"
    result = validate_editor_spec(spec)
    assert result["contract_v2_compatibility"]["state"] == "BLOCKED"
    assert "base specification SHA-256 mismatch" in result["contract_v2_compatibility"]["reasons"]
    assert result["canonical_specification"]["contract_v2"]["fingerprints"]["base_spec_sha256"] == pinned


def test_mismatched_observed_revision_and_digest_block_without_approving_execution():
    spec = with_v2()
    v2 = spec["contract_v2"]
    v2["sources"][0]["sha256"] = "b" * 64
    observed_sources = {"SourceOne": {"revision": "a" * 40, "sha256": "c" * 64}}
    result = compatibility_report(spec, observed_sources=observed_sources)
    assert result["state"] == "BLOCKED"
    assert result["execution_enabled"] is False
    assert "content SHA-256 mismatch" in " ".join(result["reasons"])
    v2["sources"][0]["sha256"] = "c" * 64
    matched = compatibility_report(
        spec, observed_versions={"dsp_commit": "d" * 40, "headless_commit": "e" * 40, "toolkit_commit": "f" * 40},
        observed_sources=observed_sources,
    )
    assert matched["state"] == "UNKNOWN"  # engine pins were not claimed
    assert matched["independent_verification"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("mutate", [
    lambda m: m["parameters"][0].update(identity=2345),
    lambda m: m["step_requirements"][0].update(execution_gate="ready"),
    lambda m: m["step_requirements"][0].update(required_permissions=["unsupported_grant"]),
    lambda m: m["oracles"][0].update(source_refs=["untracked_source"]),
])
def test_ambiguous_identity_permission_gate_and_oracle_ref_fail_closed(mutate):
    spec = with_v2()
    mutate(spec["contract_v2"])
    with pytest.raises(ValueError):
        validate_editor_spec(spec)


def test_unicode_and_revisioned_draft_round_trip_preserve_full_v2(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "r7-v2-editor.sqlite"))
    spec = with_v2()
    spec["rationale"] = "合成証拠 — źródło — café — " * 7
    # Pin only the core fields (not metadata) after the operator's edit.
    spec["contract_v2"]["fingerprints"]["base_spec_sha256"] = base_spec_sha256(spec)
    valid = validate_editor_spec(spec)
    assert valid["contract_v2_compatibility"]["state"] == "UNKNOWN"
    save = save_draft(valid["canonical_specification"], 0)
    assert save["revision"] == 1
    loaded = get_drafts()[0]["specification"]
    assert loaded == spec
    assert json.loads(json.dumps(loaded, ensure_ascii=False)) == spec
    # Revisions don't mutate or silently strip metadata.
    loaded["contract_v2"]["parameters"][0]["binding_state"] = "unresolved"
    assert loaded["contract_v2"]["parameters"][0]["identity"] is None
    saved2 = save_draft(validate_editor_spec(loaded)["canonical_specification"], 1)
    assert saved2["revision"] == 2
    assert get_drafts()[0]["specification"]["contract_v2"] == loaded["contract_v2"]
    with pytest.raises(ValueError, match="revision conflict"):
        save_draft(loaded, 1)


def test_32k_ascii_escaped_persistence_limit_still_applies(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "oversized.sqlite"))
    spec = with_v2()
    # Each canonical step is individually bounded, so accumulate genuine
    # in-bounds Unicode fields until the SQLite ensure_ascii=True representation
    # exceeds 32 KiB even though the compact UTF-8 representation fits.
    template = deepcopy(spec["steps"][0])
    spec["steps"][0]["title"] = "界" * 350
    for number in range(1, 16):
        step = deepcopy(template)
        step["id"] = "SYNTH-UNICODE-" + str(number)
        step["title"] = "界" * 350
        spec["steps"].append(step)
    utf8_size = len(json.dumps(spec, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8"))
    stored_size = len(json.dumps(spec, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True).encode("utf-8"))
    assert utf8_size < 32768 < stored_size
    # Preview validation is intentionally read-only and may display a
    # provisional oversized plan. The *real draft store* enforces the limit.
    spec["contract_v2"]["fingerprints"]["base_spec_sha256"] = base_spec_sha256(spec)
    validated = validate_editor_spec(spec)
    with pytest.raises(ValueError, match="32|KiB|size|large"):
        save_draft(validated["canonical_specification"], 0)


def test_existing_editor_viewer_is_still_not_a_runner_or_parallel_schema():
    root = Path(__file__).resolve().parents[1]
    page = (root / "gui/templates/scenario_developer.html").read_text(encoding="utf-8")
    js = (root / "gui/static/scenario_developer.js").read_text(encoding="utf-8")
    view = (root / "gui/static/scenario_contract_v2_view.js").read_text(encoding="utf-8")
    assert 'id="sd-contract-v2"' in page
    assert "scenario_guided_model.js" in page
    assert "scenario_contract_v2_view.js" in page
    assert "compatibility_report" in (root / "src/workbench/server_admin/scenario_authoring/editor_router.py").read_text()
    assert "renderContractV2" in js
    assert "contract_v2_compatibility?.state==='BLOCKED'" in js
    assert "STEP-LEVEL SOURCE ATTRIBUTION UNAVAILABLE" in view
    assert "DECLARED PINNED SOURCE CLAIM" in view
    assert "NOT INDEPENDENTLY" in view
    for unsafe in ("/builder/launch", "send_gm_command", "packet_inject"):
        assert unsafe not in js and unsafe not in view


def _pending_source_association_spec(scope="case"):
    """Synthetic proposed #1309 extension; not accepted on pre-merge main."""
    doc = with_v2()
    doc["contract_v2"]["sources"].append({
        "ref": "SourceTwo", "repository": "sarthax/darkstar-to-valhalla",
        "path": "scripts/zones/Synthetic_Zone/npcs/Secondary.lua",
        "line_start": 20, "line_end": 24, "revision": "b" * 40,
        "classification": "dsp_source", "sha256": "c" * 64,
    })
    step = doc["steps"][0]["id"]
    doc["contract_v2"]["source_associations"] = [{
        "scope": scope, "target_id": None if scope == "case" else step,
        "source_refs": ["SourceTwo"],
    }]
    return doc


def test_proposed_explicit_source_association_is_gated_on_canonical_merge():
    """Exercise the *actual* canonical validator; never implement a parallel map.

    Before #1309 merges, unsupported v2 fields fail canonical validation. After
    merge, test the accepted pure report and ensure explicit source association
    does not upgrade trust/permissions/expected values.
    """
    from workbench.server_admin.feature_testing import scenario_contract_v2 as canonical

    has_contract = callable(getattr(canonical, "source_attribution_report", None))
    case = _pending_source_association_spec("case")
    step = _pending_source_association_spec("step")
    if not has_contract:
        with pytest.raises(ValueError, match="v2 contract|fields"):
            validate_editor_spec(case)
        with pytest.raises(ValueError, match="v2 contract|fields"):
            validate_editor_spec(step)
        assert case["contract_v2"]["sources"][1]["ref"] == "SourceTwo"
        assert case["contract_v2"]["source_associations"][0]["target_id"] is None
        return

    for doc in (case, step):
        accepted = validate_editor_spec(doc)
        assert accepted["canonical_specification"] == doc
        report = canonical.source_attribution_report(doc)
        assert report["execution_enabled"] is False
        assert report["oracle_approval"] == "NOT_ESTABLISHED"
        assert report["independent_verification"] == "NOT_ESTABLISHED"
        assert accepted["preview"]["steps"][0]["verdict"] == "UNKNOWN"
    c = canonical.source_attribution_report(case)
    t = canonical.source_attribution_report(step)
    sid = step["steps"][0]["id"]
    assert c["case"] == {"state": "EXPLICIT_CITATION_CLAIM", "source_refs": ["SourceTwo"]}
    assert c["steps"][sid]["state"] == "UNKNOWN"
    assert t["case"]["state"] == "UNKNOWN"
    assert t["steps"][sid] == {"state": "EXPLICIT_CITATION_CLAIM", "source_refs": ["SourceTwo"]}


def test_proposed_source_association_rejects_malformed_scopes_and_false_authority():
    from workbench.server_admin.feature_testing import scenario_contract_v2 as canonical

    accepted = callable(getattr(canonical, "source_attribution_report", None))
    cases = []
    for kind in ("unknown_ref", "unknown_step", "duplicate", "extra_authority",
                 "empty_refs", "invalid_case_target"):
        doc = _pending_source_association_spec("step")
        rows = doc["contract_v2"]["source_associations"]
        if kind == "unknown_ref":
            rows[0]["source_refs"] = ["invented_source"]
        elif kind == "unknown_step":
            rows[0]["target_id"] = "invented_step"
        elif kind == "duplicate":
            rows.append(deepcopy(rows[0]))
        elif kind == "extra_authority":
            rows[0]["execution_enabled"] = True
        elif kind == "empty_refs":
            rows[0]["source_refs"] = []
        elif kind == "invalid_case_target":
            rows[0]["scope"] = "case"
        cases.append(doc)
    for doc in cases:
        with pytest.raises(ValueError):
            validate_editor_spec(doc)
        if accepted:
            with pytest.raises(ValueError):
                canonical.source_attribution_report(doc)


def test_proposed_association_round_trip_preserves_metadata_only_when_accepted(
    monkeypatch, tmp_path,
):
    from workbench.server_admin.feature_testing import scenario_contract_v2 as canonical

    doc = _pending_source_association_spec("step")
    raw = json.dumps(doc, ensure_ascii=False)
    assert json.loads(raw) == doc
    assert doc["contract_v2"]["source_associations"][0]["target_id"] == doc["steps"][0]["id"]
    if not callable(getattr(canonical, "source_attribution_report", None)):
        with pytest.raises(ValueError):
            validate_editor_spec(doc)
        return

    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",
                       str(tmp_path / "explicit-sources.sqlite"))
    first = save_draft(validate_editor_spec(doc)["canonical_specification"], 0)
    assert first["revision"] == 1
    loaded = get_drafts()[0]["specification"]
    assert loaded["contract_v2"] == doc["contract_v2"]
    assert canonical.source_attribution_report(loaded)["steps"][doc["steps"][0]["id"]]["state"] == "EXPLICIT_CITATION_CLAIM"
    with pytest.raises(ValueError, match="revision conflict"):
        save_draft(loaded, 0)
    loaded["steps"][0]["expected"] = "UNKNOWN — changed for independent review"
    assert canonical.compatibility_report(loaded)["state"] == "BLOCKED"
    assert loaded["contract_v2"]["source_associations"] == doc["contract_v2"]["source_associations"]


def test_source_association_does_not_accept_noncanonical_capture_step_alias():
    """Agent D's captured step and indexed digest are not canonical links."""
    doc = _pending_source_association_spec("step")
    doc["contract_v2"]["source_associations"][0]["target_id"] = "OBS-CAPTURE-S001"
    with pytest.raises(ValueError):
        validate_editor_spec(doc)
