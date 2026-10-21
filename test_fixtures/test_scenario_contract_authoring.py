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
    # Avoid assuming UTF-8 payload size equals SQLite's ensure_ascii=True representation.
    spec["rationale"] = "界" * 950
    with pytest.raises(ValueError):
        validate_editor_spec(spec)


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
