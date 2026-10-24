"""Generate SYNTHETIC B20 paired-reviewer fixtures (offline; no DB writes, no gameplay).

Run from a Toolkit checkout: PYTHONUTF8=1 PYTHONPATH=src:. python make_b20_fixtures.py <checkout> <outdir>
Reuses the repo's own synthetic acceptance fixture; each case is verified against the
real inspect_paired_readiness() and the observed outcome is written to MANIFEST.json.
This does NOT assert any B20 verdict.
"""
import sys, json, hashlib
from copy import deepcopy
from pathlib import Path

checkout, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(checkout / "src"), str(checkout), str(checkout / "test_fixtures")]
from test_capture_readiness_viewer import pair  # noqa: E402
from workbench.captures.scenario_readiness_viewer import inspect_paired_readiness  # noqa: E402

out.mkdir(parents=True, exist_ok=True)
H = lambda s: hashlib.sha256(s.encode()).hexdigest()


def case(name, expect, mutate, note, raw=None):
    review, sidecar = pair()
    if mutate:
        mutate(review, sidecar)
    d = out / name
    d.mkdir(exist_ok=True)
    rtxt = json.dumps(review, indent=1)
    stxt = json.dumps(sidecar, indent=1)
    if raw:
        rtxt, stxt = raw(rtxt, stxt)
    (d / "original_reviewed.json").write_text(rtxt, encoding="utf-8")
    (d / "readiness_sidecar.json").write_text(stxt, encoding="utf-8")
    try:
        r, s = json.loads(rtxt), json.loads(stxt)
        inspect_paired_readiness(r, s)
        actual = "ACCEPTED"
    except json.JSONDecodeError as e:
        actual = "REJECTED(invalid JSON in browser parse): " + str(e)[:60]
    except Exception as e:
        actual = "REJECTED: " + str(e)[:110]
    ok = actual.startswith(expect)
    return {"case": name, "expected": expect, "backend_check": actual, "matches_expectation": ok, "note": note}


def m_hash_review(r, s): r["capture_projection_sha256"] = H("synthetic-wrong")
def m_hash_sidecar_orig(r, s): s["original_handoff_projection_sha256"] = H("synthetic-wrong")
def m_hash_sidecar_idx(r, s): s["indexed_observation_projection_sha256"] = H("synthetic-wrong")
def m_ident(r, s): s["capture_id"] = "SYNTH-OTHER-CAPTURE"
def m_ident_review(r, s): r["capture_id"] = "SYNTH-OTHER-CAPTURE"
def m_dec_diff(r, s): s["review_decisions"] = {"steps": [{"step_id": "S01", "decision": "ACCEPT_CANDIDATE"}], "bindings": []}
def m_prov_exec(r, s): s["execution_enabled"] = True
def m_prov_appr(r, s): s["approved_for_execution"] = True
def m_prov_auto(r, s): s["automatic_import"] = True
def m_prov_verdict(r, s): s["verdict"] = "PASS"
def m_prov_review_appr(r, s): r["approved_for_execution"] = True
def m_prov_auth(r, s): s["readiness_diagnostics"]["source_integrity"]["independent_capture_bytes_authenticated"] = True
def m_extra_key(r, s): s["unexpected_authority"] = {"grant": "execute"}
def m_wrong_contract(r, s): s["contract"] = "something_else_v9"
def m_swap(r, s): s["original_evidence_handoff"] = {"capture_id": "SYNTH-OTHER-CAPTURE"}


cases = [
    case("01_matching_pair", "ACCEPTED", None, "valid synthetic pair; display-only"),
    case("02_mismatch_review_hash", "REJECTED", m_hash_review, "review capture_projection_sha256 altered"),
    case("03_mismatch_sidecar_original_hash", "REJECTED", m_hash_sidecar_orig, "sidecar original_handoff hash altered"),
    case("04_mismatch_sidecar_indexed_hash", "REJECTED", m_hash_sidecar_idx, "sidecar indexed projection hash altered"),
    case("05_mismatch_identity_sidecar", "REJECTED", m_ident, "sidecar capture_id differs"),
    case("06_mismatch_identity_review", "REJECTED", m_ident_review, "review capture_id differs"),
    case("07_mismatch_embedded_handoff", "REJECTED", m_swap, "embedded original_evidence_handoff replaced"),
    case("08_decisions_differ", "REJECTED", m_dec_diff, "reviewer decisions differ across the two files"),
    case("09_invalid_json_review", "REJECTED(invalid", None, "truncated review JSON", raw=lambda r, s: (r[: len(r) // 2], s)),
    case("10_invalid_json_sidecar", "REJECTED(invalid", None, "truncated sidecar JSON", raw=lambda r, s: (r, s[: len(s) // 2])),
    case("11_neg_prov_execution_enabled", "REJECTED", m_prov_exec, "sidecar claims execution_enabled"),
    case("12_neg_prov_approved_for_execution", "REJECTED", m_prov_appr, "sidecar claims approved_for_execution"),
    case("13_neg_prov_automatic_import", "REJECTED", m_prov_auto, "sidecar requests automatic import"),
    case("14_neg_prov_verdict_pass", "REJECTED", m_prov_verdict, "sidecar asserts PASS verdict"),
    case("15_neg_prov_review_approved", "REJECTED", m_prov_review_appr, "review claims approved_for_execution"),
    case("16_neg_prov_bytes_authenticated", "REJECTED", m_prov_auth, "diagnostics claim authenticated capture bytes"),
    case("17_neg_extra_authority_key", "REJECTED", m_extra_key, "unexpected authority key in sidecar"),
    case("18_neg_wrong_contract", "REJECTED", m_wrong_contract, "unsupported sidecar contract"),
]
# stale selection: files from two DIFFERENT cases swapped (review from 01, sidecar from 05)
sd = out / "19_stale_selection"; sd.mkdir(exist_ok=True)
(sd / "original_reviewed.json").write_text((out / "01_matching_pair" / "original_reviewed.json").read_text(encoding="utf-8"), encoding="utf-8")
(sd / "readiness_sidecar.json").write_text((out / "05_mismatch_identity_sidecar" / "readiness_sidecar.json").read_text(encoding="utf-8"), encoding="utf-8")
try:
    inspect_paired_readiness(json.loads((sd / "original_reviewed.json").read_text(encoding="utf-8")),
                             json.loads((sd / "readiness_sidecar.json").read_text(encoding="utf-8")))
    act = "ACCEPTED"
except Exception as e:
    act = "REJECTED: " + str(e)[:110]
cases.append({"case": "19_stale_selection", "expected": "REJECTED", "backend_check": act, "matches_expectation": act.startswith("REJECTED"),
              "note": "UI procedure: load 01 pair, inspect, then replace ONLY the sidecar with 05's; stale result must clear. Files here are the end-state pair."})
(out / "MANIFEST.json").write_text(json.dumps({"synthetic": True, "checkout_head": None, "cases": cases}, indent=1), encoding="utf-8")
for c in cases:
    print(("OK  " if c["matches_expectation"] else "MISMATCH ") + c["case"], "|", c["backend_check"])

# Case 20: sorted-key embedded handoff, as the offline reviewer page emits it (_json uses sort_keys=True).
def m_sorted(r, s):
    srt = lambda o: json.loads(json.dumps(o, sort_keys=True))
    s["original_evidence_handoff"] = srt(s["original_evidence_handoff"])
    r["observed_handoff"] = srt(r["observed_handoff"])
c20 = case("20_reviewer_page_sorted_key_export", "ACCEPTED", m_sorted,
           "SUSPECTED DEFECT: genuine reviewer-page export has sorted keys; viewer reconstructs a different draft and rejects it")
cases.append(c20)
(out / "MANIFEST.json").write_text(json.dumps({"synthetic": True, "cases": cases}, indent=1), encoding="utf-8")
print(("OK  " if c20["matches_expectation"] else "MISMATCH ") + c20["case"], "|", c20["backend_check"])
