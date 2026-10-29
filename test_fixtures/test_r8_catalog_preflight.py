"""#1200: synthetic, read-only catalog and preview contract tests."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from workbench.server_admin.feature_testing.r8_catalog_preflight import (
    catalog_preview, preflight_preview,
)
from workbench.server_admin.feature_testing.scenario_contract_v2 import base_spec_sha256
from workbench.server_admin.feature_testing.test_specifications import (
    specification, validate_spec,
)

ROOT = Path(__file__).resolve().parent
VECTORS = json.loads((ROOT / "r8_catalog_preflight_cases_synthetic.json")
                     .read_text(encoding="utf-8"))


def _check(result: dict, key: str) -> str | None:
    return next((row["state"] for row in result["checks"] if row["id"] == key), None)


def _attributed_mog() -> dict:
    spec = deepcopy(specification("moghancement", "MOG-09"))
    source = json.loads((ROOT / "r7_contract_v2_source_associations_valid_synthetic.json")
                        .read_text(encoding="utf-8"))["contract_v2"]["sources"][0]
    spec["contract_v2"] = {
        "contract_version": 2,
        "sources": [source],
        "parameters": [],
        "oracles": [],
        "step_requirements": [],
        "fingerprints": {"base_spec_sha256": None, "dsp_commit": None,
                         "headless_commit": None, "toolkit_commit": None},
        "source_associations": [
            {"scope": "case", "target_id": None, "source_refs": [source["ref"]]},
            {"scope": "step", "target_id": "MOG-09-S01",
             "source_refs": [source["ref"]]},
        ],
    }
    validate_spec(spec)
    return spec


def test_published_catalog_is_read_only_versioned_and_has_planning_feature_links():
    report = catalog_preview()
    assert report["execution_enabled"] is False
    assert report["execution_status"] == "NOT_AUTHORIZED"
    assert report["task_admission_supported"] is False
    assert [(r["feature_id"], r["scenario_id"]) for r in report["scenarios"]] == [
        ("inventory_observation", "INV-OBS-01"), ("moghancement", "MOG-09")
    ]
    mog = report["scenarios"][1]
    inv = report["scenarios"][0]
    assert mog["schema_version"] == 1
    assert len(mog["local_definition_sha256"]) == 64
    assert mog["digest_authority"] == "LOCAL_SERIALIZATION_ONLY"
    assert mog["runner_classification"] == "FIXED_LOCAL_OPERATOR_OBSERVATION"
    assert mog["required_authorization_class"] == "LOCAL_OPERATOR_DISPOSABLE_CHARACTER"
    assert mog["oracle_approval"] == "NOT_ESTABLISHED"
    assert mog["source_provenance"]["case"]["state"] == "UNKNOWN"
    assert inv["runner_classification"] == "UNASSIGNED_DESIGN_ONLY"
    links = {x["feature_id"]: x for x in report["feature_links"]}
    assert links["moghancement"]["feature_name"]
    assert links["gardening"]["catalog_state"] == "NO_PUBLISHED_SCENARIO"
    assert links["gardening"]["published_scenario_ids"] == []
    assert all(x["planned_cases_registered_as_runner"] is False for x in links.values())


@pytest.mark.parametrize("vector", VECTORS["cases"], ids=lambda x: x["id"])
def test_twelve_synthetic_preflight_cases_fail_closed(vector):
    assert VECTORS["synthetic"] is True and VECTORS["runtime_dispatch_allowed"] is False
    result = preflight_preview(vector["feature_id"], vector["scenario_id"],
                               claims=vector["claims"])
    assert result["preflight_state"] == vector["expected"]
    assert _check(result, vector["check"]) == vector["check_state"]
    assert result["execution_status"] == "NOT_AUTHORIZED"
    assert result["execution_enabled"] is False
    assert result["task_admission_supported"] is False
    assert result["persisted"] is False
    assert result["claims_authority"] == "UNVERIFIED_PREVIEW_ONLY"


def test_existing_v1_and_explicit_v2_attribution_are_separate_from_authority():
    legacy = catalog_preview()["scenarios"][1]
    assert legacy["source_provenance"]["case"]["state"] == "UNKNOWN"
    v2 = _attributed_mog()
    v2_entry = catalog_preview([v2])["scenarios"][0]
    assert v2_entry["source_provenance"]["case"]["state"] == "EXPLICIT_CITATION_CLAIM"
    assert v2_entry["source_provenance"]["steps"]["MOG-09-S01"]["state"] == "EXPLICIT_CITATION_CLAIM"
    assert v2_entry["oracle_approval"] == "NOT_ESTABLISHED"
    assert v2_entry["execution_status"] == "NOT_AUTHORIZED"
    # Even all matching user claims are NOT source rehash, local permission,
    # installed environment truth or an approved normative oracle.
    fully_claimed = deepcopy(VECTORS["cases"][-1]["claims"])
    outcome = preflight_preview("moghancement", "MOG-09",
                                claims=fully_claimed, specs=[v2])
    assert outcome["preflight_state"] == "UNKNOWN"
    assert outcome["execution_enabled"] is False
    assert outcome["oracle_authority"] == "NOT_ESTABLISHED"
    assert _check(outcome, "source_attribution") == "DECLARED"
    assert _check(outcome, "source_revision") == "UNKNOWN"


def test_stale_v2_base_fingerprint_is_blocked():
    spec = _attributed_mog()
    spec["contract_v2"]["fingerprints"]["base_spec_sha256"] = "a" * 64
    assert base_spec_sha256(spec) != "a" * 64
    report = preflight_preview("moghancement", "MOG-09", specs=[spec])
    assert _check(report, "source_revision") == "BLOCKED"
    assert report["execution_status"] == "NOT_AUTHORIZED"


def test_preflight_rejects_extra_claims_and_duplicate_published_scenarios():
    with pytest.raises(ValueError, match="unsupported preview"):
        preflight_preview("moghancement", "MOG-09",
                          claims={"execute_now": True})
    spec = deepcopy(specification("moghancement", "MOG-09"))
    with pytest.raises(ValueError, match="duplicate published"):
        catalog_preview([spec, deepcopy(spec)])


def test_routes_are_get_only_and_delegate_to_nonexecuting_preview():
    from workbench.server_admin.feature_testing.router import (
        r8_scenario_catalog_api, r8_scenario_preflight_api, router,
    )
    assert r8_scenario_catalog_api()["execution_enabled"] is False
    assert r8_scenario_preflight_api("moghancement", "MOG-09")["execution_status"] == "NOT_AUTHORIZED"
    for route in router.routes:
        if getattr(route, "path", "").startswith("/feature-testing/r8/"):
            assert route.methods == {"GET"}
    assert len([r for r in router.routes if getattr(r, "path", "")
                .startswith("/feature-testing/r8/")]) == 2


def test_preview_has_no_shell_database_or_artifact_write(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("R8 preview attempted an execution or DB side effect")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    catalog_before = catalog_preview()
    first = preflight_preview("moghancement", "MOG-09")
    second = preflight_preview("moghancement", "MOG-09")
    assert first == second
    assert catalog_before == catalog_preview()
    assert first["execution_enabled"] is False
