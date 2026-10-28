"""Non-executing consistency checks for the DRAFT scenario library catalog.

SCOPE: shape/provenance/consistency only. test_characterized_have_native_definition does NOT validate params
against the native Headless ScenarioActionSchema/ScenarioExpectationSchema (cross-revision schema check pending).
"""
import json
import re
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "docs" / "workbench" / "scenario_library"
EVIDENCE = {"source-supported", "capture-observed", "previously-executed", "locally-validated", "unverified"}
SUPPORT = {"supported", "partial", "unsupported", "unknown"}
PIN = "dsp-branches@main:febdc00209"
GATES = ("runner_result_authenticated", "oracle_independently_verified", "client_id_verified", "eligible_for_publish")
DOCS = ("SCENARIO_LIBRARY_INVENTORY.md", "SCENARIO_ACTION_EXPECTATION_CROSSWALK.md",
        "SCENARIO_LIBRARY_GAP_REPORT.md", "SCENARIO_LIBRARY_IMPORT_PLAN.md")


class ScenarioLibraryCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((LIB / "scenario_catalog_draft.json").read_text(encoding="utf-8"))
        cls.items = cls.cat["scenarios"]

    def test_counts_and_flags(self):
        self.assertEqual(len(self.items), 46)
        self.assertEqual(sum(s["tier"] == "characterized" for s in self.items), 15)
        self.assertEqual(len(self.cat["failure_injection_probes"]), 2)
        self.assertEqual(sorted(s["id"] for s in self.items if s["support_status"] == "supported"),
                         ["SL-MOG-009", "SL-PARTY-001"])
        self.assertEqual(self.cat["status"], "DRAFT")
        self.assertFalse(self.cat["execution_validated"])

    def test_unique_ids_and_required_fields(self):
        ids = [s["id"] for s in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        for s in self.items:
            self.assertEqual(s["status"], "draft")
            self.assertFalse(s["execution_validated"])
            self.assertTrue(set(s["evidence_class"]) <= EVIDENCE, s["id"])
            self.assertIn(s["support_status"], SUPPORT, s["id"])
            self.assertTrue(s["provenance"], s["id"])
            self.assertEqual(set(s["readable"]), {"given", "when", "then"})

    def test_characterized_have_native_definition(self):
        for s in self.items:
            if s["tier"] != "characterized":
                continue
            x = s["xiheadless"]
            for k in ("native_action", "params", "expected_state", "readback_collector", "oracle_rule", "setup",
                      "interpretation"):
                self.assertIn(k, x, s["id"])
            self.assertEqual(set(x["interpretation"]), {"PASS", "FAIL", "BLOCKED", "UNKNOWN"})

    def test_quest_candidates_trace_to_dsp_source(self):
        for s in self.items:
            if s["id"].startswith("SL-QUEST-"):
                self.assertTrue(any("scripts/zones/" in p for p in s["provenance"]), s["id"])
                self.assertTrue(s["provenance"][0].startswith(PIN + ": "), s["id"])
                self.assertFalse(s.get("client_id_verified"), s["id"])
                self.assertNotEqual(s["support_status"], "supported", s["id"])

    def test_dsp_nation_missions_present_and_pinned(self):
        ids = {s["id"] for s in self.items}
        for pre in ("SD", "BA", "WI"):
            for n in range(1, 6):
                self.assertIn("SL-MSN-%s-%d" % (pre, n), ids)
        self.assertFalse(any("WOTG" in i for i in ids))
        for s in self.items:
            self.assertNotIn("LandSandBoat", " ".join(s["provenance"]), s["id"])
            if s["id"].startswith("SL-MSN-"):
                self.assertTrue(all(p.startswith(PIN + ": ") for p in s["provenance"]), s["id"])
                self.assertNotEqual(s["support_status"], "supported", s["id"])
        self.assertEqual(self.cat["generated_from"]["dsp"], PIN)
        ext = json.loads((LIB / "dsp_mission_extract.json").read_text(encoding="utf-8"))
        self.assertEqual(ext["source"], PIN)
        for s in self.items:
            body = json.dumps(s).lower()
            self.assertNotIn("landsandboat", body, s["id"])
            self.assertNotIn("wotg", body, s["id"])
            self.assertNotIn("lsb@", body, s["id"])

    def test_supported_means_schema_only_never_elevated(self):
        by = {s["id"]: s for s in self.items}
        for sid in ("SL-NPC-001", "SL-ZONE-001"):
            self.assertNotEqual(by[sid]["support_status"], "supported", sid)
        for s in self.items:
            for g in GATES:
                self.assertIs(s[g], False, (s["id"], g))
            self.assertIs(s["source_schema_compatible"], s["support_status"] == "supported", s["id"])
            if s["support_status"] == "supported":
                self.assertIn("xiheadless", s, s["id"])
            if s["evidence_class"] == ["source-supported"]:
                self.assertNotEqual(s["support_status"], "supported", s["id"])
            self.assertEqual(s["status"], "draft")

    def test_import_plan_and_docs_state_the_meaning(self):
        plan = (LIB / "SCENARIO_LIBRARY_IMPORT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("DRAFT records only", plan)
        self.assertIn("never publishes", plan)
        inv = (LIB / "SCENARIO_LIBRARY_INVENTORY.md").read_text(encoding="utf-8")
        self.assertIn("Totals: 46 candidates, 15 characterized, 2 failure-injection", inv)
        self.assertIn("does NOT mean", inv)
        cw = (LIB / "SCENARIO_ACTION_EXPECTATION_CROSSWALK.md").read_text(encoding="utf-8")
        self.assertIn("not execution or oracle validation", cw)
        self.assertNotIn("| wait_ms | zone, in_zone | snapshot | supported |", cw)

    def test_extractor_is_pinned_and_portable(self):
        src = (LIB / "_extract_dsp_missions.py").read_text(encoding="utf-8")
        self.assertIn('PIN = "febdc00209"', src)
        self.assertIn("refusing to regenerate", src)
        self.assertNotIn("D:\\", src)
        self.assertNotIn('"main"', src)

    def test_probes_kept_separate(self):
        for p in self.cat["failure_injection_probes"]:
            self.assertEqual(p["kind"], "failure-injection")
        self.assertFalse(any(s["id"].startswith("SL-PROBE") for s in self.items))

    def test_docs_present(self):
        for name in DOCS:
            self.assertTrue((LIB / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
