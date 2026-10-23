"""#1353/#1366: isolated synthetic conformance simulator, NOT an MCP gateway.

Run: python -m unittest -v test_fixtures/test_r8_asi_first_five_read_discovery.py
Only the checked-in JSON fixture is read. No Toolkit runtime, requests, DB,
filesystem mutations, provider, browser, credentials or gameplay calls.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

FIXTURE = json.loads(Path(__file__).with_name(
    "r8_asi_first_five_read_discovery_synthetic.json"
).read_text(encoding="utf-8"))

OPERATIONS = {
    "supervisor_scenario_list": {"feature_id", "limit", "cursor"},
    "supervisor_scenario_get": {
        "feature_id", "case_id", "publication_snapshot_id", "expected_sha256"},
    "supervisor_scenario_revision": {
        "feature_id", "case_id", "publication_snapshot_id", "expected_sha256"},
    "supervisor_scenario_sources": {
        "feature_id", "case_id", "publication_snapshot_id", "expected_sha256"},
    "supervisor_scenario_preflight": {
        "feature_id", "case_id", "publication_snapshot_id", "expected_sha256"},
}
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}\Z", re.ASCII)
DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
SNAPSHOT = re.compile(r"[A-Za-z0-9_-]{8,128}\Z", re.ASCII)
CURSOR = re.compile(r"[A-Za-z0-9_-]{8,256}\Z", re.ASCII)
AUTHORITY = {
    "execution_status": "NOT_AUTHORIZED",
    "execution_enabled": False,
    "task_admission_supported": False,
    "independent_verification": "NOT_ESTABLISHED",
    "oracle_approval": "NOT_ESTABLISHED",
}

# The public-like simulator knows exactly TWO source-grounded canonical keys.
ROWS = {
    (row["feature_id"], row["case_id"]): row
    for row in FIXTURE["published_fixture_rows"]
}
# Never part of ROWS, not a publishable catalog entry; test-only v2 example.
PROBE = FIXTURE["synthetic_v2_probe"]
PUBLICATION = FIXTURE["publication_snapshot_fixture"]["id"]


def _result(http_status: int, status: str, reason: str, **fields: object) -> dict:
    """All answers have fixed non-executing, non-approving authority."""
    return {
        "http_status": http_status,
        "status": status,
        "reason": reason,
        "authority": dict(AUTHORITY),
        "specification_released": False,
        "published_count": fields.get("published_count"),
        "case_source_refs": fields.get("case_source_refs", []),
        "step_source_refs": fields.get("step_source_refs", {}),
        "disclosed": http_status != 403,
    }


def project_synthetic(vector: dict) -> dict:
    """Five read-only, *simulated* public operations; no real ASGI security.

    Context flags are trusted test labels, not validated credentials, signed
    cursors, serialized byte measurements or independently proven facts.
    """
    ctx, req, op = vector["context"], vector["request"], vector["operation"]
    # Pure-model ordering is NOT proof of FastAPI/Pydantic ordering.
    if (ctx.get("auth", "AUTHORIZED") != "AUTHORIZED" or
            ctx.get("scope", "SAME_ACTOR") != "SAME_ACTOR"):
        return _result(403, "BLOCKED", "unauthorized")
    if op not in OPERATIONS:
        return _result(400, "BLOCKED", "unsupported_operation")
    if not isinstance(req, dict) or set(req) - OPERATIONS[op]:
        return _result(400, "BLOCKED", "invalid_request")
    if "feature_id" in req and not (
            isinstance(req["feature_id"], str) and IDENTITY.fullmatch(req["feature_id"])):
        return _result(400, "BLOCKED", "invalid_identity")
    if op != "supervisor_scenario_list" and not (
            isinstance(req.get("feature_id"), str) and
            isinstance(req.get("case_id"), str) and
            IDENTITY.fullmatch(req["feature_id"]) and
            IDENTITY.fullmatch(req["case_id"])):
        return _result(400, "BLOCKED", "invalid_identity")

    if op == "supervisor_scenario_list":
        limit = req.get("limit", 20)
        if type(limit) is not int or not (1 <= limit <= 25):
            return _result(400, "BLOCKED", "invalid_page_limit")
        if req.get("cursor") is not None and (
                not isinstance(req["cursor"], str) or
                not CURSOR.fullmatch(req["cursor"]) or
                ctx.get("cursor_condition") != "VERIFIED_SCOPE_AND_SNAPSHOT"):
            return _result(409, "BLOCKED", "cursor_invalid")

    # Explicitly *simulated* counts, NOT actual encoder or size-policy proof.
    if (ctx.get("response_bytes", 0) > 65536 or
            ctx.get("spec_bytes", 0) > 32768 or
            ctx.get("source_count", 0) > 50):
        return _result(413, "BLOCKED", "budget_exceeded")
    if ctx.get("source_authority") == "STALE":
        return _result(200, "BLOCKED", "source_stale")

    if op == "supervisor_scenario_list":
        matches = [row for row in ROWS.values()
                   if req.get("feature_id") in (None, row["feature_id"])]
        return _result(200, "OK", "published_declarations_only",
                       published_count=min(len(matches), req.get("limit", 20)))

    # Every per-case read must be tied to the same symbolic publication.
    # Real immutable snapshot construction and atomic lookup NOT implemented.
    version = req.get("publication_snapshot_id")
    if not isinstance(version, str) or not SNAPSHOT.fullmatch(version):
        return _result(400, "BLOCKED", "invalid_snapshot")
    digest = req.get("expected_sha256")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        return _result(400, "BLOCKED", "invalid_digest")
    if version != PUBLICATION or ctx.get("publication_snapshot_state") == "STALE":
        return _result(409, "BLOCKED", "stale_publication")
    row = ROWS.get((req["feature_id"], req["case_id"]))
    if row is None:
        return _result(200, "UNSUPPORTED", "not_published")
    if digest != row["local_definition_sha256"]:
        return _result(200, "BLOCKED", "revision_conflict")

    if op in ("supervisor_scenario_get", "supervisor_scenario_revision"):
        return _result(200, "OK", "metadata_only" if op.endswith("_get")
                       else "local_revision_only")
    if op == "supervisor_scenario_sources":
        refs = row["source_claims"]
        return _result(200, "UNKNOWN", "source_claims_only",
                       case_source_refs=list(refs["case"]),
                       step_source_refs=deepcopy(refs["steps"]))
    if row["runner_classification"] != "FIXED_LOCAL_OPERATOR_OBSERVATION":
        return _result(200, "BLOCKED", "runner_unassigned")
    if ctx.get("observer_state") == "NOT_IMPLEMENTED":
        return _result(200, "BLOCKED", "observer_unsupported")
    if ctx.get("observer_state") == "PR_ONLY":
        return _result(200, "BLOCKED", "observer_not_verified")
    return _result(200, "UNKNOWN", "advisory_only")


def project_isolated_v2_probe(vector: dict) -> dict:
    """Hypothetical v2 CASE/STEP thought experiment; not an API path.

    No call to project_synthetic() can access PROBE, even with mode set.
    """
    if (vector.get("mode") != "ISOLATED_SYNTHETIC_V2_PROBE" or
            not PROBE["synthetic_only"] or not PROBE["never_published"]):
        raise ValueError("isolated v2 probe requires explicit test-only scope")
    req, ctx = vector["request"], vector["context"]
    if (req.get("feature_id"), req.get("case_id")) != (
            PROBE["feature_id"], PROBE["case_id"]):
        raise ValueError("wrong isolated v2 test identity")
    if ctx.get("source_count", 0) > 50:
        return _result(413, "BLOCKED", "budget_exceeded")
    if ctx.get("source_authority") == "STALE":
        return _result(200, "BLOCKED", "source_stale")
    if vector["operation"] == "supervisor_scenario_get":
        return _result(200, "OK", "metadata_only")
    if vector["operation"] == "supervisor_scenario_sources":
        refs = PROBE["source_claims"]
        return _result(200, "UNKNOWN", "source_claims_only",
                       case_source_refs=list(refs["case"]),
                       step_source_refs=deepcopy(refs["steps"]))
    raise ValueError("unsupported isolated v2 test operation")


def evaluate_fixture(vector: dict) -> dict:
    """Only the local harness can access isolated v2 source-claim examples."""
    if vector.get("mode") == "ISOLATED_SYNTHETIC_V2_PROBE":
        return project_isolated_v2_probe(vector)
    return project_synthetic(vector)


class FirstFiveConformanceFixtureTests(unittest.TestCase):
    """Exactly 7 methods; vector fixture cases are subTests, not test methods."""

    def test_matrix_declares_synthetic_only_scope_and_grounded_examples(self):
        self.assertEqual(FIXTURE["contract"],
                         "toolkit-r8-asi-first-five-test-matrix/1-SYNTHETIC")
        for key in ("synthetic", "not_authoritative", "not_installed_gateway",
                    "no_execution_or_catalog_mutation"):
            self.assertIs(FIXTURE[key], True)
        self.assertEqual(set(OPERATIONS), {
            "supervisor_scenario_list", "supervisor_scenario_get",
            "supervisor_scenario_revision", "supervisor_scenario_sources",
            "supervisor_scenario_preflight",
        })
        self.assertEqual(set(ROWS), {
            ("moghancement", "MOG-09"),
            ("inventory_observation", "INV-OBS-01"),
        })
        self.assertEqual(len(ROWS), 2)
        self.assertTrue(all(r["real_id_from_published_spec"] for r in ROWS.values()))
        self.assertNotIn(("fixture_only", "SYNTH-CASE-1"), ROWS)
        self.assertTrue(PROBE["synthetic_only"])
        self.assertTrue(PROBE["never_published"])
        self.assertFalse(PROBE["real_id_from_published_spec"])
        self.assertEqual(PROBE["contract_version"], 2)
        self.assertEqual(FIXTURE["publication_snapshot_fixture"]["id"], PUBLICATION)
        for row in (*ROWS.values(), PROBE):
            self.assertRegex(row["local_definition_sha256"], DIGEST)
            self.assertIn(row["contract_version"], (None, 2))
        self.assertEqual(project_synthetic({
            "operation": "supervisor_scenario_list", "request": {}, "context": {}
        })["published_count"], 2)
        # Ordinary GET/revision/sources/preflight all reject fictitious identity.
        for op in OPERATIONS.keys() - {"supervisor_scenario_list"}:
            with self.subTest(operation=op):
                request = {"feature_id": PROBE["feature_id"],
                           "case_id": PROBE["case_id"],
                           "expected_sha256": PROBE["local_definition_sha256"],
                           "publication_snapshot_id": PUBLICATION}
                self.assertEqual(project_synthetic({
                    "operation": op, "request": request, "context": {}
                })["status"], "UNSUPPORTED")

    def test_all_review_vectors_match_explicit_status_and_never_grant_authority(self):
        vectors = FIXTURE["vectors"]
        expected_ids = {f"P{i:02d}" for i in range(1, 14)} | {
            f"N{i:02d}" for i in range(1, 50)}
        self.assertEqual(len(vectors), 62)
        self.assertEqual({v["id"] for v in vectors}, expected_ids)
        self.assertEqual(len({v["id"] for v in vectors}), len(vectors))
        self.assertEqual(sum(v["id"].startswith("P") for v in vectors), 13)
        self.assertEqual(sum(v["id"].startswith("N") for v in vectors), 49)
        self.assertEqual({v["id"] for v in vectors if "mode" in v},
                         {"P05", "P13", "N21", "N26", "N27"})
        for v in vectors:
            with self.subTest(id=v["id"]):
                out = evaluate_fixture(v)
                for key, want in v["expect"].items():
                    self.assertEqual(out[key], want, (v["id"], key))
                self.assertEqual(out["authority"], AUTHORITY)
                self.assertFalse(out["specification_released"])
                self.assertNotIn(out["status"], {"READY", "EXECUTED", "APPROVED"})
                for forbidden in ("task_id", "operation_id", "mutable_specification",
                                  "oracle_expected", "next_cursor", "rows"):
                    self.assertNotIn(forbidden, out)
                self.assertEqual(out["disclosed"], out["http_status"] != 403)
                if out["http_status"] == 403:
                    self.assertIsNone(out["published_count"])
                    self.assertEqual(out["case_source_refs"], [])
                    self.assertEqual(out["step_source_refs"], {})

    def test_auth_precedes_existence_identity_and_requested_operation(self):
        v = {x["id"]: x for x in FIXTURE["vectors"]}
        denied = project_synthetic(v["N01"])
        for key in ("N02", "N03", "N31", "N38"):
            with self.subTest(id=key):
                self.assertEqual(denied, project_synthetic(v[key]))
        self.assertEqual(project_synthetic(v["N04"])["http_status"], 400)
        self.assertEqual(project_synthetic(v["N05"])["http_status"], 403)
        self.assertEqual(project_synthetic(v["N37"])["reason"], "invalid_page_limit")
        # Router-unmatched 404 is NOT tested by this symbolic function.

    def test_sources_are_explicit_scoped_claims_not_oracles_or_step_guesses(self):
        v = {x["id"]: x for x in FIXTURE["vectors"]}
        scoped = project_isolated_v2_probe(v["P05"])
        self.assertEqual(scoped["case_source_refs"], ["synthetic_case_ref"])
        self.assertEqual(scoped["step_source_refs"], {
            "SYNTH_STEP_1": ["synthetic_step_ref"], "SYNTH_STEP_2": [],
        })
        self.assertNotIn("synthetic_case_ref",
                         scoped["step_source_refs"]["SYNTH_STEP_2"])
        self.assertEqual(project_synthetic(v["P06"])["step_source_refs"], {})
        self.assertEqual(project_synthetic(v["N15"])["http_status"], 400)
        self.assertEqual(project_synthetic(v["N35"])["status"], "UNSUPPORTED")
        self.assertEqual(scoped["authority"]["oracle_approval"], "NOT_ESTABLISHED")

    def test_cursor_scope_boundaries_and_payload_limits_fail_closed(self):
        v = {x["id"]: x for x in FIXTURE["vectors"]}
        for key in ("N08", "N09", "N10", "N11", "N45", "N46", "N47"):
            with self.subTest(id=key):
                self.assertEqual(project_synthetic(v[key])["reason"],
                                 "cursor_invalid")
                self.assertEqual(project_synthetic(v[key])["http_status"], 409)
        for key in ("N24", "N25", "N26", "N49"):
            with self.subTest(id=key):
                result = evaluate_fixture(v[key])
                self.assertEqual(result["reason"], "budget_exceeded")
                self.assertEqual(result["http_status"], 413)
                self.assertNotIn("next_cursor", result)
        self.assertEqual(project_synthetic(v["N07"])["http_status"], 400)
        self.assertEqual(project_synthetic(v["N37"])["http_status"], 400)

    def test_proposal_oracle_and_execution_fields_are_not_read_inputs(self):
        v = {x["id"]: x for x in FIXTURE["vectors"]}
        for key in ("N14", "N16", "N17", "N18", "N20", "N29", "N30"):
            with self.subTest(id=key):
                out = project_synthetic(v[key])
                self.assertEqual(out["http_status"], 400)
                self.assertEqual(out["reason"], "invalid_request")
                self.assertFalse(out["authority"]["task_admission_supported"])
        self.assertEqual(project_synthetic(v["N19"])["reason"],
                         "unsupported_operation")
        self.assertEqual(project_synthetic(v["P07"])["status"], "UNKNOWN")
        self.assertEqual(project_synthetic(v["P08"])["status"], "BLOCKED")
        for key in ("N34", "N35", "N36"):
            self.assertEqual(project_synthetic(v[key])["status"], "UNSUPPORTED")

    def test_one_unknown_snapshot_cannot_claim_signed_physical_revision(self):
        v = {x["id"]: x for x in FIXTURE["vectors"]}
        self.assertEqual(project_synthetic(v["P10"])["reason"], "local_revision_only")
        for key in ("N12", "N13"):
            self.assertEqual(project_synthetic(v[key])["reason"],
                             "revision_conflict")
        for key in ("N41", "N42", "N43", "N44"):
            with self.subTest(id=key):
                out = project_synthetic(v[key])
                self.assertEqual(out["http_status"], 409)
                self.assertEqual(out["reason"], "stale_publication")
                self.assertEqual(out["case_source_refs"], [])
        for key in ("N39", "N40"):
            self.assertEqual(project_synthetic(v[key])["reason"], "invalid_snapshot")
        for key in ("N33", "N48"):
            out = project_synthetic(v[key])
            self.assertEqual(out["http_status"], 400)
            self.assertEqual(out["reason"], "invalid_digest")
        self.assertEqual(evaluate_fixture(v["N21"])["status"], "BLOCKED")
        self.assertEqual(evaluate_fixture(v["N27"])["status"], "UNKNOWN")
        self.assertEqual(project_synthetic(v["N22"])["status"], "BLOCKED")
        self.assertEqual(project_synthetic(v["N23"])["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
