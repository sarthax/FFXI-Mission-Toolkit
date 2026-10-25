"""Non-executing consistency checks for the DRAFT scenario library catalog."""
import json
import re
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "docs" / "workbench" / "scenario_library"
EVIDENCE = {"source-supported", "capture-observed", "previously-executed", "locally-validated", "unverified"}
SUPPORT = {"supported", "partial", "unsupported", "unknown"}
DOCS = ("SCENARIO_LIBRARY_INVENTORY.md", "SCENARIO_ACTION_EXPECTATION_CROSSWALK.md",
        "SCENARIO_LIBRARY_GAP_REPORT.md", "SCENARIO_LIBRARY_IMPORT_PLAN.md")


class ScenarioLibraryCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((LIB / "scenario_catalog_draft.json").read_text(encoding="utf-8"))
        cls.items = cls.cat["scenarios"]

    def test_counts_and_flags(self):
        self.assertTrue(25 <= len(self.items) <= 70)
        self.assertTrue(10 <= sum(s["tier"] == "characterized" for s in self.items) <= 25)
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
                self.assertTrue(re.match(r"^dsp-branches@main:[0-9a-f]{10}", s["provenance"][0]), s["id"])

    def test_dsp_nation_missions_present_and_pinned(self):
        ids = {s["id"] for s in self.items}
        for pre in ("SD", "BA", "WI"):
            for n in range(1, 6):
                self.assertIn("SL-MSN-%s-%d" % (pre, n), ids)
        self.assertFalse(any("WOTG" in i for i in ids))
        for s in self.items:
            self.assertNotIn("LandSandBoat", " ".join(s["provenance"]), s["id"])
            if s["id"].startswith("SL-MSN-"):
                self.assertTrue(re.match(r"^dsp-branches@main:[0-9a-f]{10}: ", s["provenance"][0]), s["id"])

    def test_probes_kept_separate(self):
        for p in self.cat["failure_injection_probes"]:
            self.assertEqual(p["kind"], "failure-injection")
        self.assertFalse(any(s["id"].startswith("SL-PROBE") for s in self.items))

    def test_docs_present(self):
        for name in DOCS:
            self.assertTrue((LIB / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
