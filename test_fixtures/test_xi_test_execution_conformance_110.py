"""SYNTHETIC-ONLY Headless/Toolkit execution-contract mirror (#110).

Checks the exact Headless fixture bytes independently and exercises Toolkit
consumer safety invariants. This is not a runtime protocol adapter or an oracle.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import pytest

from workbench.server_admin.feature_testing.importer import validate_report
from workbench.server_admin.feature_testing.results import VERDICTS as TOOLKIT_VERDICTS


CORPUS = Path(__file__).parent / "xi_test_execution_conformance"
PROTOCOL = "xi-test-execution"
VERSION = "1.0.0-draft.1"
BLOB_SHA1 = {
    # Git blob IDs fetched from XIHeadless main, docs/protocol/fixtures/, 2026-10-28.
    # A deliberate upstream fixture update must refresh these pins AND the manifest.
    "MANIFEST.json": "17215d37ac3bd3ba0850b8ad09b4555b15fd7e97",
    "cancelled.json": "6d07a2f7e0d5d1dbf728da67b2b3b0d74b8a2d4b",
    "interrupted.json": "a35bf58241e734f283d18f478201d421b7c3ab1f",
    "multi_bot.json": "a3efe4f5aed0bedb27453f44bc50cbe47883d6dd",
    "refused.json": "8cb328e16b5495971a9a77287fd2c65e55e57f1f",
    "success.json": "9b017b1d00e6a8558b67e194ed94c3dc5d5f153d",
    "timed_out.json": "1cdd11692ebacdd296895e1f12fb3d62f767ea43",
    "unknown_oracle.json": "f5f5bdf7d34a2aaaa3f15767f0b3a7db53ea2cef",
}
EXPECTED = {
    "cancelled": ("BLOCKED", "cancelled", "verified"),
    "interrupted": ("UNKNOWN", "interrupted", "unknown"),
    "multi_bot": ("FAIL", "completed", "verified"),
    "refused": None,
    "success": ("PASS", "completed", "verified"),
    "timed_out": ("UNKNOWN", "failed", "unknown"),
    "unknown_oracle": ("UNKNOWN", "completed", "verified"),
}
KINDS = {
    "submit_request", "submit_response", "status_request", "status_response",
    "cancel_request", "cancel_response", "result_bundle",
}
STATES = {"accepted", "running", "completed", "failed", "cancelled", "interrupted"}
VERDICTS = {"PASS", "FAIL", "BLOCKED", "UNKNOWN"}
CLEANUP = {"not_required", "pending", "verified", "incomplete", "unknown"}
VERSION_PATTERN = re.compile(r"^1\.[0-9]+\.[0-9]+(?:-draft\.[0-9]+)?$")


def _fixture(name: str) -> dict:
    return json.loads((CORPUS / f"{name}.json").read_text(encoding="utf-8"))


def _message(name: str, kind: str) -> dict:
    return deepcopy(next(m for m in _fixture(name)["messages"] if m["kind"] == kind))


def _consumer_core(message: dict) -> None:
    """Focused consumer acceptance checks, not a replacement wire schema."""
    if not isinstance(message, dict) or message.get("protocol") != PROTOCOL:
        raise ValueError("unsupported protocol")
    version = message.get("protocol_version")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("unsupported major/version")
    if message.get("kind") not in KINDS or not isinstance(message.get("data"), dict):
        raise ValueError("unknown core kind or missing data")
    if not isinstance(message.get("request_id"), str) or not isinstance(message.get("emitted_at"), str):
        raise ValueError("missing envelope identity")
    data = message["data"]
    kind = message["kind"]
    if kind == "submit_response":
        if data.get("admission") not in {"accepted", "refused"}:
            raise ValueError("unknown admission")
        if data["admission"] == "refused" and (data.get("execution_id") or data.get("operation_id")):
            raise ValueError("refusal cannot create an operation")
    if kind == "status_response" and data.get("state") not in STATES:
        raise ValueError("unknown status")
    if kind == "cancel_response":
        if data.get("code") not in {"cancellation_requested", "already_terminal", "unknown_operation"}:
            raise ValueError("unknown cancellation response")
        if data["code"] == "cancellation_requested" and data.get("observed_state") == "cancelled":
            raise ValueError("cancel acknowledgement cannot establish terminal cancellation")
    if kind != "result_bundle":
        return
    operation = data.get("operation")
    cleanup = data.get("cleanup")
    revisions = data.get("revisions")
    assertions = data.get("assertions")
    if (not isinstance(operation, dict) or operation.get("state") not in
            {"completed", "failed", "cancelled", "interrupted"}
            or not isinstance(cleanup, dict) or cleanup.get("state") not in CLEANUP
            or not isinstance(revisions, dict)
            or set(revisions) != {"dsp_commit", "headless_commit", "toolkit_commit"}
            or not isinstance(assertions, list) or data.get("verdict") not in VERDICTS):
        raise ValueError("missing/unknown result core")
    unknowns = data.get("unknowns")
    if not isinstance(unknowns, list) or not all(isinstance(x, str) for x in unknowns):
        raise ValueError("missing provenance reasons")
    for source, revision in revisions.items():
        if revision is None:
            if not any(source in reason for reason in unknowns):
                raise ValueError("missing revision requires an explicit unknown reason")
        elif not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise ValueError("invalid revision SHA")
    if data["verdict"] == "PASS" and operation["state"] != "completed":
        raise ValueError("non-completed execution cannot establish PASS")
    if any(a.get("verdict") not in VERDICTS or a.get("authority") not in {
            "client_observed", "server_authoritative", "unverified"}
           or a.get("origin") not in {"headless_client", "dsp_read_only", "runner_derived"}
           for a in assertions):
        raise ValueError("unknown assertion core")
    required = [a["verdict"] for a in assertions if a.get("required", True)]
    if "FAIL" in required:
        expected = "FAIL"
    elif not required or "UNKNOWN" in required:
        expected = "UNKNOWN"
    elif "BLOCKED" in required or cleanup["state"] not in {"verified", "not_required"}:
        expected = "BLOCKED"
    else:
        expected = "PASS"
    if data["verdict"] != expected:
        raise ValueError("aggregate verdict disagrees with assertions/cleanup")
    if data["verdict"] == "PASS" and any(
        a["verdict"] == "PASS" and (
            a["authority"] == "unverified"
            or (a["origin"] == "runner_derived" and a["authority"] != "server_authoritative")
        ) for a in assertions
    ):
        raise ValueError("unverified source cannot establish PASS")


def test_mirrored_source_blobs_are_identical_to_pinned_headless_files():
    assert {p.name for p in CORPUS.glob("*.json")} == set(BLOB_SHA1)
    for filename, pinned_blob in BLOB_SHA1.items():
        p = CORPUS / filename
        assert p.is_file() and not p.is_symlink()
        raw = p.read_bytes()
        assert b"\r" not in raw
        assert raw.endswith(b"\n")
        git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        assert git_blob == pinned_blob, filename


def test_manifest_raw_byte_digest_length_protocol_and_fixture_set():
    manifest = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["protocol"] == PROTOCOL
    assert manifest["protocol_revision"] == VERSION
    assert manifest["digest_scope"] == "raw file bytes (sha256-bytes-v1)"
    assert [e["path"] for e in manifest["files"]] == sorted(f"{n}.json" for n in EXPECTED)
    for entry in manifest["files"]:
        filename = entry["path"]
        assert filename in BLOB_SHA1 and filename != "MANIFEST.json"
        raw = (CORPUS / filename).read_bytes()
        assert len(raw) == entry["length"]
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_all_upstream_synthetic_messages_pass_toolkit_consumer_core(name):
    fixture = _fixture(name)
    assert fixture["case"] == name
    assert fixture["synthetic"] is True
    assert fixture["messages"]
    for message in fixture["messages"]:
        _consumer_core(message)
        assert message["protocol_version"] == VERSION


@pytest.mark.parametrize("name,expected", sorted(EXPECTED.items()))
def test_semantic_verdict_is_not_inferred_from_lifecycle(name, expected):
    messages = _fixture(name)["messages"]
    responses = [m["data"] for m in messages if m["kind"] == "submit_response"]
    assert len(responses) == 1
    if expected is None:
        assert responses[0]["admission"] == "refused"
        assert not any(m["kind"] == "result_bundle" for m in messages)
        assert not responses[0].get("operation_id")
        return
    assert responses[0]["admission"] == "accepted"
    result = _message(name, "result_bundle")["data"]
    assert (result["verdict"], result["operation"]["state"], result["cleanup"]["state"]) == expected
    assert result["synthetic"] is True
    assert result["verdict"] in VERDICTS
    # A completed task may be FAIL or UNKNOWN, independently of MCP admission.
    if result["operation"]["state"] == "completed":
        assert result["verdict"] in {"PASS", "FAIL", "UNKNOWN"}


def test_cancel_request_ack_is_not_proof_of_terminal_cancel():
    ack = _message("cancelled", "cancel_response")
    assert ack["data"]["code"] == "cancellation_requested"
    assert ack["data"]["code"] != "cancelled"
    assert _message("cancelled", "status_response")["data"]["state"] == "cancelled"
    assert _message("cancelled", "result_bundle")["data"]["verdict"] == "BLOCKED"


@pytest.mark.parametrize("name", ["success", "cancelled", "interrupted", "multi_bot", "timed_out", "unknown_oracle"])
def test_unknown_revisions_are_explicit_and_not_deployment_proof(name):
    result = _message(name, "result_bundle")["data"]
    assert all(result["revisions"][key] is None for key in
               ("dsp_commit", "headless_commit", "toolkit_commit"))
    assert isinstance(result["unknowns"], list)
    for key in ("dsp_commit", "headless_commit", "toolkit_commit"):
        assert any(key in reason for reason in result["unknowns"])
    if name in {"interrupted", "timed_out", "unknown_oracle"}:
        assert result["verdict"] == "UNKNOWN"
    if name in {"interrupted", "timed_out"}:
        assert result["cleanup"]["state"] == "unknown"


def test_unknown_core_changes_refused_but_additive_optional_fields_are_not_gameplay_pass():
    base = _message("success", "result_bundle")
    extended = deepcopy(base)
    extended["data"]["x_future_optional"] = "unverified"
    extended["x_optional_envelope"] = 1
    _consumer_core(extended)
    for change in (
        lambda m: m.update(protocol_version="2.0.0"),
        lambda m: m.update(kind="result"),
        lambda m: m["data"].update(verdict="SUCCESS"),
        lambda m: m["data"]["operation"].update(state="paused"),
        lambda m: m["data"]["cleanup"].update(state="mostly"),
        lambda m: m["data"].pop("revisions"),
        lambda m: m["data"]["assertions"][0].update(authority="unverified"),
    ):
        damaged = deepcopy(base)
        change(damaged)
        with pytest.raises(ValueError):
            _consumer_core(damaged)


def test_pass_requires_completed_operation_even_with_verified_assertions():
    for state in ("failed", "cancelled", "interrupted", "running"):
        damaged = _message("success", "result_bundle")
        damaged["data"]["operation"]["state"] = state
        with pytest.raises(ValueError, match="result core|non-completed"):
            _consumer_core(damaged)


def test_missing_revision_reason_and_malformed_sha_rejected():
    for source in ("dsp_commit", "headless_commit", "toolkit_commit"):
        damaged = _message("success", "result_bundle")
        damaged["data"]["unknowns"] = [
            reason for reason in damaged["data"]["unknowns"] if source not in reason
        ]
        with pytest.raises(ValueError, match="unknown reason"):
            _consumer_core(damaged)
        damaged = _message("success", "result_bundle")
        damaged["data"]["revisions"][source] = "not-a-full-sha"
        with pytest.raises(ValueError, match="revision SHA"):
            _consumer_core(damaged)


def test_cancel_ack_cannot_claim_observed_cancellation():
    acknowledgement = _message("cancelled", "cancel_response")
    acknowledgement["data"]["observed_state"] = "cancelled"
    with pytest.raises(ValueError, match="cannot establish terminal"):
        _consumer_core(acknowledgement)


def test_legacy_importer_is_not_a_direct_wire_protocol_consumer():
    """Toolkit v1 has its own ten-field report boundary; never silently reinterpret wire."""
    catalog = {"features": [{"id": "feat.synthetic", "cases": [{"id": "case.synthetic"}]}]}
    for name in EXPECTED:
        for message in _fixture(name)["messages"]:
            with pytest.raises(ValueError, match="unsupported report schema"):
                validate_report(message, catalog)
    # A fabricated v1 row with null source revisions is refused even if the
    # upstream wire scenario's *synthetic* aggregate happened to be PASS.
    fake = {
        "run_id": "run.synthetic", "case_id": "case.synthetic", "feature_id": "feat.synthetic",
        "stage": "gameplay", "verdict": "PASS", "observed_at": "2026-10-20T10:05:00Z",
        "dsp_commit": None, "headless_commit": None, "toolkit_commit": None,
        "evidence": {"assertions": [{}], "observations": {"unverified": True}},
    }
    with pytest.raises(ValueError, match="SHA"):
        validate_report({"schema_version": 1, "results": [fake]}, catalog)


def test_toolkit_unknown_supported_but_not_wire_authorization():
    # The current Toolkit v1 local importer recognizes UNKNOWN, unlike older
    # guidance; that does NOT make a synthetic Headless wire result importable.
    assert "UNKNOWN" in TOOLKIT_VERDICTS
    catalog = {"features": [{"id": "feat.synthetic", "cases": [{"id": "case.synthetic"}]}]}
    row = {
        "run_id": "run.synthetic", "case_id": "case.synthetic", "feature_id": "feat.synthetic",
        "stage": "gameplay", "verdict": "UNKNOWN", "observed_at": "2026-10-20T10:05:00Z",
        "dsp_commit": "a" * 40, "headless_commit": "b" * 40, "toolkit_commit": "c" * 40,
        "evidence": {"reason_class": "ORACLE_UNKNOWN", "synthetic": True},
    }
    assert validate_report({"schema_version": 1, "results": [row]}, catalog) == [row]
    # This is structural validation ONLY, not actual authenticated evidence,
    # a permitted v2-to-v1 projection, or a call to import_report().
