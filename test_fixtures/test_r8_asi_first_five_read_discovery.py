"""#1353 synthetic-only first-five scenario discovery conformance examples.

Run standalone: python test_fixtures/test_r8_asi_first_five_read_discovery.py
This is a *review simulator*; it is NOT a route, security implementation,
registered MCP method, bearer test, provenance attestation or live acceptance.
Never imports Toolkit runtime, invokes I/O other than its checked-in fixture,
looks up characters, makes a network call, mutates specs or dispatches work.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import unittest

FIXTURE = json.loads(Path(__file__).with_name(
    "r8_asi_first_five_read_discovery_synthetic.json"
).read_text(encoding="utf-8"))
OPERATIONS = {
    "supervisor_scenario_list": {"feature_id", "limit", "cursor"},
    "supervisor_scenario_get": {"feature_id", "case_id", "expected_sha256"},
    "supervisor_scenario_revision": {"feature_id", "case_id", "expected_sha256"},
    "supervisor_scenario_sources": {"feature_id", "case_id"},
    "supervisor_scenario_preflight": {"feature_id", "case_id"},
}
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z", re.ASCII)
DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
AUTHORITY = {
    "execution_status": "NOT_AUTHORIZED",
    "execution_enabled": False,
    "task_admission_supported": False,
    "independent_verification": "NOT_ESTABLISHED",
    "oracle_approval": "NOT_ESTABLISHED",
}
ROWS = {
    (s["feature_id"], s["case_id"]): s
    for s in FIXTURE["published_fixture_rows"]
}


def _result(http_status: int, status: str, reason: str, **public: object) -> dict:
    """Fixed denied-authority shape independent of the example's requested flags."""
    return {
        "http_status": http_status,
        "status": status,
        "reason": reason,
        "authority": dict(AUTHORITY),
        # Cannot emit canonical specification, a permission grant, or action.
        "specification_released": False,
        "published_count": public.get("published_count"),
        "case_source_refs": public.get("case_source_refs", []),
        "step_source_refs": public.get("step_source_refs", {}),
        "disclosed": http_status != 403,
    }


def project_synthetic(vector: dict) -> dict:
    """Design-review decision table; intentionally NOT a Toolkit route adapter.

    Order is important: authorization before method/identity/existence validation.
    Context states are trusted *by the fixture only*, never by real HTTP clients.
    The caller cannot supply any of these context flags as route query fields.
    """
    ctx = vector["context"]
    req = vector["request"]
    op = vector["operation"]
    if ctx.get("auth", "AUTHORIZED") != "AUTHORIZED" or ctx.get(
        "scope", "SAME_ACTOR"
    ) != "SAME_ACTOR":
        return _result(403, "BLOCKED", "unauthorized")

    if op not in OPERATIONS:
        return _result(400, "BLOCKED", "unsupported_operation")
    if not isinstance(req, dict) or set(req) - OPERATIONS[op]:
        return _result(400, "BLOCKED", "invalid_request")
    if "feature_id" in req and not (
        isinstance(req["feature_id"], str)
        and IDENTITY.fullmatch(req["feature_id"])
    ):
        return _result(400, "BLOCKED", "invalid_identity")
    if op != "supervisor_scenario_list" and not (
        isinstance(req.get("feature_id"), str)
        and isinstance(req.get("case_id"), str)
        and IDENTITY.fullmatch(req["feature_id"])
        and IDENTITY.fullmatch(req["case_id"])
    ):
        return _result(400, "BLOCKED", "invalid_identity")
    if op == "supervisor_scenario_list":
        limit = req.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 25:
            return _result(400, "BLOCKED", "invalid_page_limit")
        if req.get("cursor") is not None and (
            not isinstance(req["cursor"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,256}", req["cursor"])
            or ctx.get("cursor_condition") != "VERIFIED_SCOPE_AND_SNAPSHOT"
        ):
            return _result(200, "BLOCKED", "cursor_invalid")

    # Check bounded *rendered* data, not only original source lengths.
    if (
        ctx.get("response_bytes", 0) > 65536
        or ctx.get("spec_bytes", 0) > 32768
        or ctx.get("source_count", 0) > 50
    ):
        return _result(200, "BLOCKED", "budget_exceeded")
    if ctx.get("source_authority") == "STALE":
        return _result(200, "BLOCKED", "source_stale")

    if op == "supervisor_scenario_list":
        scope = req.get("feature_id")
        matches = [
            s for s in FIXTURE["published_fixture_rows"]
            if scope is None or s["feature_id"] == scope
        ]
        # Fixture projection, not an executable scenario advertisement.
        return _result(
            200, "OK", "published_declarations_only",
            published_count=min(len(matches), req.get("limit", 20)),
        )

    spec = ROWS.get((req["feature_id"], req["case_id"]))
    if spec is None:
        return _result(200, "UNSUPPORTED", "not_published")
    if op in ("supervisor_scenario_get", "supervisor_scenario_revision"):
        claimed = req.get("expected_sha256")
        if claimed is not None and (
            not isinstance(claimed, str)
            or not DIGEST.fullmatch(claimed)
            or claimed != spec["local_definition_sha256"]
        ):
            return _result(200, "BLOCKED", "revision_conflict")
        return _result(200, "OK", (
            "metadata_only" if op == "supervisor_scenario_get"
            else "local_revision_only"
        ))
    if op == "supervisor_scenario_sources":
        refs = spec["source_claims"]
        # Explicitly carry each scope; never infer STEP from CASE or oracle.
        return _result(
            200, "UNKNOWN", "source_claims_only",
            case_source_refs=list(refs["case"]),
            step_source_refs=copy.deepcopy(refs["steps"]),
        )
    if spec["runner_classification"] != "FIXED_LOCAL_OPERATOR_OBSERVATION":
        return _result(200, "BLOCKED", "runner_unassigned")
    if ctx.get("observer_state") == "NOT_IMPLEMENTED":
        return _result(200, "BLOCKED", "observer_unsupported")
    if ctx.get("observer_state") == "PR_ONLY":
        return _result(200, "BLOCKED", "observer_not_verified")
    # Even all synthetically matching declarations cannot grant a READY state.
    return _result(200, "UNKNOWN", "advisory_only")


class FirstFiveConformanceFixtureTests(unittest.TestCase):
    """No actual authentication, request handling, transport or game event."""

    def test_matrix_declares_synthetic_only_scope_and_grounded_examples(self):
        self.assertEqual(FIXTURE["contract"], "toolkit-r8-asi-first-five-test-matrix/1-SYNTHETIC")
        self.assertIs(FIXTURE["synthetic"], True)
        self.assertIs(FIXTURE["not_authoritative"], True)
        self.assertIs(FIXTURE["not_installed_gateway"], True)
        self.assertIs(FIXTURE["no_execution_or_catalog_mutation"], True)
        self.assertEqual(
            {(r["feature_id"], r["case_id"]) for r in ROWS.values()
             if r["real_id_from_published_spec"]},
            {("moghancement", "MOG-09"), ("inventory_observation", "INV-OBS-01")},
        )
        self.assertEqual(set(OPERATIONS), {
            "supervisor_scenario_list", "supervisor_scenario_get",
            "supervisor_scenario_revision", "supervisor_scenario_sources",
            "supervisor_scenario_preflight",
        })
        self.assertEqual(len(ROWS), len(FIXTURE["published_fixture_rows"]))
        for row in ROWS.values():
            self.assertRegex(row["local_definition_sha256"], DIGEST)
            self.assertIn(row["contract_version"], (None, 2))
        self.assertFalse(ROWS[("fixture_only", "SYNTH-CASE-1")]["real_id_from_published_spec"])

    def test_all_review_vectors_match_explicit_status_and_never_grant_authority(self):
        vectors = FIXTURE["vectors"]
        self.assertGreaterEqual(len(vectors), 35)
        self.assertEqual(len(vectors), len({v["id"] for v in vectors}))
        self.assertTrue(all(v["id"].startswith(("P", "N")) for v in vectors))
        for v in vectors:
            with self.subTest(case=v["id"]):
                result = project_synthetic(v)
                for k, expected in v["expect"].items():
                    self.assertEqual(result[k], expected, f"{v['id']} {k}")
                self.assertEqual(result["authority"], AUTHORITY)
                self.assertIs(result["specification_released"], False)
                self.assertNotIn(result["status"], ("READY", "EXECUTED", "APPROVED"))
                self.assertNotIn("task_id", result)
                self.assertNotIn("operation_id", result)
                self.assertNotIn("mutable_specification", result)
                self.assertNotIn("oracle_expected", result)
                self.assertEqual(result["disclosed"], result["http_status"] != 403)
                if result["http_status"] == 403:
                    self.assertIsNone(result["published_count"])
                    self.assertEqual(result["case_source_refs"], [])
                    self.assertEqual(result["step_source_refs"], {})

    def test_auth_precedes_existence_identity_and_requested_operation(self):
        cases = {v["id"]: v for v in FIXTURE["vectors"]}
        self.assertEqual(
            project_synthetic(cases["N01"]),
            project_synthetic(cases["N02"]),
        )
        self.assertEqual(
            project_synthetic(cases["N02"]),
            project_synthetic(cases["N03"]),
        )
        self.assertEqual(
            project_synthetic(cases["N03"]),
            project_synthetic(cases["N31"]),
        )
        self.assertEqual(project_synthetic(cases["N04"])["http_status"], 400)
        self.assertEqual(project_synthetic(cases["N05"])["http_status"], 403)

    def test_sources_are_explicit_scoped_claims_not_oracles_or_step_guesses(self):
        cases = {v["id"]: v for v in FIXTURE["vectors"]}
        full = project_synthetic(cases["P05"])
        self.assertEqual(full["case_source_refs"], ["synthetic_case_ref"])
        self.assertEqual(full["step_source_refs"], {
            "SYNTH_STEP_1": ["synthetic_step_ref"],
            "SYNTH_STEP_2": [],
        })
        self.assertNotIn("synthetic_case_ref", full["step_source_refs"]["SYNTH_STEP_2"])
        self.assertEqual(project_synthetic(cases["P06"])["step_source_refs"], {})
        self.assertEqual(project_synthetic(cases["N15"])["http_status"], 400)
        self.assertEqual(full["authority"]["oracle_approval"], "NOT_ESTABLISHED")

    def test_cursor_scope_boundaries_and_payload_limits_fail_closed(self):
        cases = {v["id"]: v for v in FIXTURE["vectors"]}
        for k in ("N08", "N09", "N10", "N11"):
            with self.subTest(cursor=k):
                self.assertEqual(project_synthetic(cases[k])["reason"], "cursor_invalid")
        for k in ("N24", "N25", "N26"):
            with self.subTest(size=k):
                self.assertEqual(project_synthetic(cases[k])["reason"], "budget_exceeded")
        self.assertEqual(project_synthetic(cases["N07"])["http_status"], 400)

    def test_proposal_oracle_and_execution_fields_are_not_read_inputs(self):
        cases = {v["id"]: v for v in FIXTURE["vectors"]}
        for k in ("N14", "N16", "N17", "N18", "N20", "N29", "N30"):
            with self.subTest(untrusted=k):
                r = project_synthetic(cases[k])
                self.assertEqual(r["http_status"], 400)
                self.assertEqual(r["reason"], "invalid_request")
                self.assertFalse(r["authority"]["task_admission_supported"])
        self.assertEqual(project_synthetic(cases["N19"])["reason"], "unsupported_operation")
        self.assertEqual(project_synthetic(cases["P07"])["status"], "UNKNOWN")
        self.assertEqual(project_synthetic(cases["P08"])["status"], "BLOCKED")

    def test_one_unknown_snapshot_cannot_claim_signed_physical_revision(self):
        cases = {v["id"]: v for v in FIXTURE["vectors"]}
        self.assertEqual(project_synthetic(cases["P10"])["status"], "OK")
        self.assertEqual(project_synthetic(cases["P10"])["reason"], "local_revision_only")
        self.assertEqual(project_synthetic(cases["N12"])["reason"], "revision_conflict")
        self.assertEqual(project_synthetic(cases["N13"])["reason"], "revision_conflict")
        self.assertEqual(project_synthetic(cases["N21"])["status"], "BLOCKED")
        self.assertEqual(project_synthetic(cases["N22"])["status"], "BLOCKED")
        self.assertEqual(project_synthetic(cases["N23"])["status"], "BLOCKED")
        self.assertEqual(project_synthetic(cases["N27"])["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
