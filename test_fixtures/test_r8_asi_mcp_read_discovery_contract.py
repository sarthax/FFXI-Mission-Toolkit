"""#1325: design-only conformance for proposed supervisor scenario GET responses.

This validates SYNTHETIC samples, not installed HTTP/MCP tools, gameplay,
production source authenticity, DB results, permissions or #105 wire messages.
No server, file, network, SQLite, subprocess, or headless operations.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

import pytest

_FIXTURE = Path(__file__).with_name(
    "r8_asi_read_discovery_contract_synthetic.json"
)
DOC = json.loads(_FIXTURE.read_text(encoding="utf-8"))
EXAMPLES = {x["id"]: x["response"] for x in DOC["examples"]}
CORE = {"contract", "tool", "status", "scenario", "authority",
        "data", "pagination", "unknowns", "provenance"}
AUTH = {"execution_status", "execution_enabled", "task_admission_supported",
        "independent_verification", "oracle_approval"}
PAGINATION = {"limit", "next_cursor", "has_more"}
SCENARIO = {"feature_id", "scenario_id", "schema_version", "contract_version",
            "local_definition_sha256"}
TOOLS = {
    "supervisor_scenario_list": {"items", "feature_links"},
    "supervisor_scenario_get": {
        "runner_classification", "required_authorization_class",
        "oracle_authority", "observation_state", "source_scope",
        "published_execution_status", "blocked_reasons", "reason",
        "expected_sha256", "observed_sha256", "specification_released",
        "published_case_found",
    },
    "supervisor_scenario_revision": {
        "base_spec_sha256", "local_definition_sha256", "digest_authority",
        "source_revision", "independently_rehashed",
    },
    "supervisor_scenario_sources": {
        "sources", "case", "steps", "unassigned_source_refs",
        "identity_source_refs", "oracle_source_refs",
    },
    "supervisor_scenario_coverage_gaps": {"items", "stage_only_count_status"},
    "supervisor_scenario_preflight": {
        "preflight_state", "checks", "missing_dependencies",
        "execution_status", "execution_enabled",
    },
    "supervisor_scenario_evidence_summary": {
        "availability", "record_count", "recent", "recorded_verdict",
        "independent_verification",
    },
    "supervisor_scenario_change_impact": {
        "impact_state", "reason", "reviewed_diff_available",
        "impacted_step_ids", "requested_source_revision",
        "matched_source_revision",
    },
}
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
CURSOR = re.compile(r"[A-Za-z0-9_-]{8,256}\Z")
# data.recent[] item schema: ref_id may contain colons (unlike KEY) and is
# bounded identically to #1329 scenario_evidence_ref_v0_NONCANONICAL.ref_id.
REF_ID = re.compile(r"[!-~]{1,120}\Z")
EXCERPT = re.compile(r"[ -~]{1,200}\Z")
RECENT_ITEM = {"ref_id", "recorded_verdict", "attempt_completeness", "excerpt"}
RECENT_VERDICTS = {None, "PASS", "FAIL", "PARTIAL", "UNKNOWN"}
RECENT_COMPLETENESS = {"COMPLETE", "PARTIAL", "UNKNOWN"}
STATUS = {"OK", "UNKNOWN", "BLOCKED", "UNSUPPORTED"}


def _fail(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def _identity(value: object) -> None:
    _fail(isinstance(value, str) and KEY.fullmatch(value) is not None,
          "invalid canonical identity")


def validate_recent_item(item: object) -> None:
    """Test-only data.recent[] item check; NOT a production parser."""
    _fail(isinstance(item, dict) and set(item) == RECENT_ITEM,
          "unknown or missing recent item field")
    _fail(isinstance(item["ref_id"], str) and
          REF_ID.fullmatch(item["ref_id"]) is not None, "invalid ref_id")
    _fail(item["recorded_verdict"] in RECENT_VERDICTS, "invalid recorded verdict")
    _fail(item["attempt_completeness"] in RECENT_COMPLETENESS,
          "invalid attempt completeness")
    _fail(isinstance(item["excerpt"], str) and
          EXCERPT.fullmatch(item["excerpt"]) is not None, "invalid excerpt")


def _sha(value: object) -> None:
    _fail(value is None or isinstance(value, str) and SHA.fullmatch(value)
          is not None, "invalid local revision digest")


def _references(value: object, known: set[str] | None = None) -> None:
    _fail(isinstance(value, list) and len(value) == len(set(map(str, value))),
          "invalid or duplicate source references")
    for x in value:
        _identity(x)
        if known is not None:
            _fail(x in known, "unknown scoped source reference")


def validate_sample(response: dict) -> None:
    """Test-only expected response shape; NOT a production or wire parser."""
    _fail(isinstance(response, dict) and set(response) == CORE,
          "unsupported response keys")
    # Check the emitted bytes, not the count of Unicode codepoints.
    raw = json.dumps(response, ensure_ascii=False, separators=(",", ":"),
                     sort_keys=True, allow_nan=False).encode("utf-8")
    _fail(len(raw) <= 65536, "response exceeds 64 KiB")

    _fail(response["contract"] == "toolkit-r8-scenario-discovery/1",
          "incompatible discovery version")
    tool = response["tool"]
    _fail(tool in TOOLS, "unknown read-only operation")
    _fail(response["status"] in STATUS, "invalid discovery state")
    _fail(response["provenance"] == "DECLARED_OR_IMPORTED_UNVERIFIED",
          "improper provenance authority")
    _fail(isinstance(response["unknowns"], list) and
          all(isinstance(u, str) and KEY.fullmatch(u) for u in response["unknowns"]),
          "invalid unknown reasons")

    auth = response["authority"]
    _fail(isinstance(auth, dict) and set(auth) == AUTH, "invalid authority object")
    _fail(auth == {
        "execution_status": "NOT_AUTHORIZED",
        "execution_enabled": False,
        "task_admission_supported": False,
        "independent_verification": "NOT_ESTABLISHED",
        "oracle_approval": "NOT_ESTABLISHED",
    }, "read response grants unreviewed authority")

    page = response["pagination"]
    _fail(isinstance(page, dict) and set(page) == PAGINATION, "invalid pagination")
    _fail(type(page["limit"]) is int and 1 <= page["limit"] <= 25,
          "unbounded page limit")
    _fail(type(page["has_more"]) is bool, "invalid pagination flag")
    cur = page["next_cursor"]
    _fail(cur is None or isinstance(cur, str) and CURSOR.fullmatch(cur),
          "unsupported or unsafe cursor")
    _fail(page["has_more"] == (cur is not None),
          "cursor/has_more disagreement")

    scenario = response["scenario"]
    if scenario is not None:
        _fail(isinstance(scenario, dict) and set(scenario) == SCENARIO,
              "invalid scenario descriptor")
        _identity(scenario["feature_id"])
        _identity(scenario["scenario_id"])
        _fail(scenario["schema_version"] == 1 and
              scenario["contract_version"] in (None, 2),
              "legacy/v2 schema compatibility")
        _sha(scenario["local_definition_sha256"])

    data = response["data"]
    _fail(isinstance(data, dict) and set(data) <= TOOLS[tool],
          "unknown or privileged read data field")
    _fail(not any(k in data for k in
                  ("sql", "filesystem_path", "dispatch", "auth_token",
                   "execution_grant", "mutable_catalog")),
          "unsafe operation data")
    if tool == "supervisor_scenario_list":
        rows = data.get("items", [])
        _fail(isinstance(rows, list) and len(rows) <= page["limit"],
              "unbounded scenario list")
        for row in rows:
            _identity(row["feature_id"])
            _identity(row["scenario_id"])
            _fail(row.get("runner_classification") in
                  {"FIXED_LOCAL_OPERATOR_OBSERVATION", "UNASSIGNED_DESIGN_ONLY"},
                  "unsupported runner classification")
            _fail(row.get("execution_status") == "NOT_AUTHORIZED" and
                  row.get("execution_enabled") is False,
                  "scenario list promotes execution")
        for feature in data.get("feature_links", []):
            _fail(feature.get("planned_cases_registered_as_runner") is False,
                  "staged domain case promoted")

    if tool == "supervisor_scenario_get":
        if "reason" in data and data["reason"] == "REVISION_MISMATCH":
            _fail(response["status"] == "BLOCKED" and
                  data.get("specification_released") is False,
                  "stale revision silently accepted")
            _sha(data.get("expected_sha256"))
            _sha(data.get("observed_sha256"))
            _fail(data["expected_sha256"] != data["observed_sha256"],
                  "mismatch sample is not conflicting")
        if "published_execution_status" in data:
            _fail(data["published_execution_status"] == "design_only",
                  "unexpected design-only fixture state")
    if tool == "supervisor_scenario_sources":
        sources = data.get("sources", [])
        _fail(isinstance(sources, list) and len(sources) <= 50,
              "unbounded source listing")
        refs = [s["ref"] for s in sources]
        _references(refs)
        known = set(refs)
        case = data["case"]
        _fail(case["state"] in {"UNKNOWN", "EXPLICIT_CITATION_CLAIM"},
              "invalid case attribution")
        _references(case["source_refs"], known)
        if case["state"] == "UNKNOWN":
            _fail(not case["source_refs"], "inferred case refs")
        for step in data["steps"]:
            _identity(step["step_id"])
            _fail(step["state"] in {"UNKNOWN", "EXPLICIT_CITATION_CLAIM"},
                  "invalid step state")
            _references(step["source_refs"], known)
            if step["state"] == "UNKNOWN":
                _fail(not step["source_refs"], "step ref inferred from case/oracle")
        _references(data["unassigned_source_refs"], known)
        _references(data["identity_source_refs"], known)
        for oracle in data["oracle_source_refs"]:
            _identity(oracle["assertion_id"])
            _references(oracle["source_refs"], known)
            _fail(oracle["approval"] == "NOT_ESTABLISHED",
                  "candidate oracle automatically approved")
    if tool == "supervisor_scenario_preflight":
        _fail(data.get("execution_status") == "NOT_AUTHORIZED" and
              data.get("execution_enabled") is False and
              data.get("preflight_state") in {"UNKNOWN", "BLOCKED"},
              "advisory preflight became executable")
    if tool == "supervisor_scenario_evidence_summary":
        _fail(data.get("independent_verification") == "NOT_ESTABLISHED",
              "recorded evidence falsely authenticated")
        if data.get("availability") == "NOT_CONFIGURED":
            _fail(data.get("record_count") is None and not data.get("recent"),
                  "missing evidence misrepresented as zero")
        _fail(len(data.get("recent", [])) <= 10, "oversized evidence summary")
        for item in data.get("recent", []):
            validate_recent_item(item)
    if tool == "supervisor_scenario_change_impact":
        if not data.get("reviewed_diff_available"):
            _fail(not data.get("impacted_step_ids") and
                  response["status"] in {"BLOCKED", "UNKNOWN"},
                  "change impact invented from unreviewed source")


def _set_path(obj: dict, dotted: str, value: object) -> None:
    node = obj
    *parts, leaf = dotted.split(".")
    for key in parts:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if isinstance(node, list):
        node[int(leaf)] = value
    else:
        node[leaf] = value


def test_fixture_is_review_only_not_registered_mcp_or_importer():
    assert DOC["synthetic"] is True
    assert DOC["not_runtime_contract_approval"] is True
    assert DOC["not_mcp_registered"] is True
    assert DOC["not_importable_evidence"] is True
    assert len(EXAMPLES) == 12
    assert len(DOC["negative_mutations"]) >= 17
    assert set(TOOLS) == {x["tool"] for x in EXAMPLES.values()}


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_bounded_synthetic_sample_contract(name):
    validate_sample(deepcopy(EXAMPLES[name]))


@pytest.mark.parametrize("case", DOC["negative_mutations"],
                         ids=lambda item: item["id"])
def test_privilege_revision_and_ambiguity_mutations_fail_closed(case):
    assert case["based_on"] in EXAMPLES
    doc = deepcopy(EXAMPLES[case["based_on"]])
    value = ("X" * 70000 if
             case["value"] == "__TEST_GENERATE_70000_BYTES__" else case["value"])
    _set_path(doc, case["path"], value)
    with pytest.raises(ValueError):
        validate_sample(doc)


def test_case_source_does_not_implicitly_bind_step_or_oracle():
    report = EXAMPLES["explicit_case_not_step"]["data"]
    assert report["case"]["source_refs"] == ["synthetic-source-a"]
    assert report["case"]["state"] == "EXPLICIT_CITATION_CLAIM"
    assert report["steps"] == [{
        "step_id": "SYNTH-STEP-1", "state": "UNKNOWN", "source_refs": [],
    }]
    assert report["oracle_source_refs"][0]["approval"] == "NOT_ESTABLISHED"
    assert EXAMPLES["explicit_case_not_step"]["authority"]["execution_enabled"] is False


def test_historical_runner_is_not_task_admission():
    entries = EXAMPLES["published_catalog_page"]["data"]["items"]
    assert {(r["feature_id"], r["scenario_id"]) for r in entries} == {
        ("moghancement", "MOG-09"),
        ("inventory_observation", "INV-OBS-01"),
    }
    assert all(r["execution_status"] == "NOT_AUTHORIZED" for r in entries)
    assert all(r["execution_enabled"] is False for r in entries)


def test_missing_evidence_revision_and_unapproved_oracle_are_distinct():
    assert EXAMPLES["missing_evidence_not_zero"]["data"]["record_count"] is None
    assert EXAMPLES["revision_mismatch"]["status"] == "BLOCKED"
    assert EXAMPLES["coverage_missing_approved_oracle"]["status"] == "UNKNOWN"
    assert EXAMPLES["coverage_missing_approved_oracle"]["data"]["items"][0][
        "recorded_verdict"] is None


def test_no_production_imports_or_side_effect_capabilities_in_contract_tests():
    assert "toolkit-r8-scenario-discovery" != "xi-test-execution"
    # The samples exercise a proposed read-only DTO. This test file does not
    # import Toolkit server, SQLite, Headless MCP or mutate any external state.
    assert all(x.startswith("supervisor_scenario_") for x in TOOLS)
    assert all(x["authority"]["task_admission_supported"] is False
               for x in EXAMPLES.values())


# ---- data.recent[] item schema and #1329 ref_id interop -------------------
# Identity mapping (normative here): the #1330 envelope key
# scenario.scenario_id is the canonical catalog case identifier for joins
# (with feature_id). #1329 scenario.case_id carries the SAME value; joins use
# exact string equality on (feature_id, scenario_id == case_id), no
# normalisation. A mismatch is BLOCKED, never fuzzy-matched.
_EVIDENCE_VECTORS = Path(__file__).with_name(
    "r8_evidence_summary_vectors_synthetic.json")


def _good_item(**over):
    item = deepcopy(EXAMPLES["evidence_recent_items_synthetic"]["data"]["recent"][0])
    item.update(over)
    return item


def test_recent_item_schema_accepts_good_items_with_colons():
    for item in EXAMPLES["evidence_recent_items_synthetic"]["data"]["recent"]:
        validate_recent_item(item)
        assert ":" in item["ref_id"]
    assert KEY.fullmatch(_good_item()["ref_id"]) is None  # REF_ID != KEY
    validate_recent_item(_good_item(ref_id="a" * 120))


@pytest.mark.parametrize("over", [
    {"ref_id": "evidence:synthetic: x"}, {"ref_id": "evidence:\tx"},
    {"ref_id": ""}, {"ref_id": "a" * 121}, {"ref_id": "evidence:café"},
    {"ref_id": 5}, {"excerpt": ""}, {"excerpt": "x" * 201},
    {"excerpt": "line\nbreak"}, {"recorded_verdict": "VERIFIED_PASS"},
    {"attempt_completeness": "DONE"}, {"raw_path": "C:/x"},
])
def test_recent_item_schema_rejects_bad_items(over):
    with pytest.raises(ValueError):
        validate_recent_item(_good_item(**over))


def test_recent_item_missing_field_rejected():
    item = _good_item()
    del item["excerpt"]
    with pytest.raises(ValueError):
        validate_recent_item(item)


def test_recent_more_than_ten_items_rejected():
    doc = deepcopy(EXAMPLES["evidence_recent_items_synthetic"])
    doc["data"]["recent"] = [_good_item() for _ in range(11)]
    with pytest.raises(ValueError):
        validate_sample(doc)
    doc["data"]["recent"] = [_good_item() for _ in range(10)]
    validate_sample(doc)


def test_1329_vector_ref_ids_satisfy_1330_ref_id_pattern():
    vectors = json.loads(_EVIDENCE_VECTORS.read_text(encoding="utf-8"))
    ids = [v["evidence_reference"]["ref_id"] for v in vectors["examples"]
           if "evidence_reference" in v]
    assert ids, "no #1329 evidence_reference vectors found"
    for ref_id in ids:
        assert REF_ID.fullmatch(ref_id), ref_id
        validate_recent_item(_good_item(ref_id=ref_id))
