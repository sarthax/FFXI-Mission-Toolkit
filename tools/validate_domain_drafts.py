"""Read-only staged domain validator; does not authenticate source or enable execution."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

LANES = {"observe-now", "needs-readback", "needs-mutation", "needs-deploy"}
SHA = re.compile(r"[0-9a-f]{40}")


class ValidationError(ValueError):
    pass


def check(condition, reason):
    if not condition:
        raise ValidationError(reason)


def load(path):
    path = Path(path)
    check(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(value, dict), f"nonobject: {path}")
    return value


def lane_of(c):
    lane, old = c.get("lane"), c.get("execution_lane")
    check(lane is not None or old is not None, "readiness lane missing")
    check(lane is None or old is None or lane == old, "conflicting lane alias")
    lane = lane if lane is not None else old
    check(lane in LANES, "unknown readiness lane")
    return lane


def get_refs(c):
    refs = []
    for field in ("oracle_sources", "source_refs"):
        refs.extend(c.get(field) or [])
    refs.extend((c.get("oracle") or {}).get("source_refs") or [])
    for s in c["steps"]:
        for field in ("oracle_refs", "oracle_sources", "source_refs"):
            refs.extend(s.get(field) or [])
    return refs


def validate_domain(name, doc, meta):
    check(doc.get("schema_version") == 1 and doc.get("execution_enabled") is False,
          f"{name}: staging must be disabled")
    check(doc.get("canonical_target") == "data/testing/test_specifications.json"
          and doc.get("integration_status") == "BLOCKED_SCHEMA_OWNER_REVIEW",
          f"{name}: canonical import must remain blocked")
    revision = (doc.get("source_revision") or {}).get("dsp_commit")
    check(isinstance(revision, str) and SHA.fullmatch(revision) and
          revision == meta["sha"], f"{name}: source revision mismatch")
    check(str(doc["source_revision"].get("deployed", "")).startswith("UNKNOWN"),
          f"{name}: unverifiable deployment claim")
    cases = doc.get("cases")
    check(isinstance(cases, list) and len(cases) == meta["cases"],
          f"{name}: wrong case count")
    rows = []
    for c in cases:
        cid = c.get("case_id")
        check(isinstance(cid, str) and re.fullmatch(r"[A-Z]+-[0-9]{2}", cid),
              f"{name}: bad case ID")
        check(c.get("feature_id") == name, f"{cid}: wrong domain")
        check(c.get("runner") == "unassigned" and
              c.get("execution_status") == "design_only" and
              str(c.get("verdict", "")).startswith("NOT_RUN"),
              f"{cid}: promoted runner or verdict")
        check(c.get("execution_enabled") is not True and
              c.get("execution_authorized") is not True, f"{cid}: permission enabled")
        mutation = c.get("mutation")
        if isinstance(mutation, dict):
            check(mutation.get("enabled") is False, f"{cid}: mutation enabled")
        else:
            check(mutation in ("none", "client", "gm"), f"{cid}: unknown mutation class")
        readiness = lane_of(c)
        if name == "gardening":
            check(c.get("lane") == c.get("execution_lane") == "needs-mutation",
                  f"{cid}: Gardening lane compatibility mismatch")
        bdd = c.get("behavior") or {}
        for phase in ("given", "when", "then"):
            values = bdd.get(phase)
            check(isinstance(values, list) and bool(values) and
                  all(isinstance(v, str) and v.strip() for v in values),
                  f"{cid}: BDD {phase} missing")
        check("UNKNOWN" in json.dumps(c).upper(),
              f"{cid}: absent explicit UNKNOWN status")
        steps = c.get("steps")
        check(isinstance(steps, list) and len(steps) == 4,
              f"{cid}: missing/reordered steps")
        declared_assertions = c.get("assertions", [])
        check(isinstance(declared_assertions, list) and
              all(isinstance(a, dict) and isinstance(a.get("id"), str) and
                  bool(a["id"]) for a in declared_assertions),
              f"{cid}: invalid assertion IDs")
        assertion_ids = [a["id"] for a in declared_assertions]
        check(len(set(assertion_ids)) == len(assertion_ids),
              f"{cid}: duplicate staged assertion ID")
        asserted = set(assertion_ids)
        for i, s in enumerate(steps, 1):
            sid = f"{cid}-S{i:02d}"
            check(s.get("id") == sid and isinstance(s.get("expected"), str) and
                  s["expected"].strip(), f"{sid}: missing expected or step ID")
            ids = s.get("assertion_ids")
            check(isinstance(ids, list) and bool(ids) and
                  all(isinstance(a, str) and a for a in ids),
                  f"{sid}: missing assertion IDs")
            if asserted:
                check(set(ids) <= asserted, f"{sid}: unbound assertion ID")
            check(s.get("execution_authorized") is not True and
                  s.get("manual_execution_allowed") is not True and
                  s.get("required_permissions") in (None, []),
                  f"{sid}: unsafe step permission")
            check(any(s.get(field) for field in
                      ("oracle_refs", "oracle_sources", "source_refs")),
                  f"{sid}: source citation missing")
        refs = get_refs(c)
        check(bool(refs), f"{cid}: no source")
        for ref in refs:
            check(isinstance(ref, dict) and
                  ref.get("repository") == "sarthax/darkstar-to-valhalla" and
                  ref.get("commit") == revision, f"{cid}: unpinned source")
            path = ref.get("path")
            check(isinstance(path, str) and path and not path.startswith("/") and
                  ".." not in path.split("/") and "\\" not in path,
                  f"{cid}: invalid source path")
            start, end = ref.get("line_start"), ref.get("line_end")
            check(type(start) is int and type(end) is int and 0 < start <= end,
                  f"{cid}: unpinned file:line")
            canonical_url = ("https://github.com/sarthax/darkstar-to-valhalla/blob/"
                             + revision + "/" + path + "#L" + str(start)
                             + "-L" + str(end))
            check(ref.get("url") == canonical_url,
                  f"{cid}: source URL does not match exact pinned path and line range")
            check(ref.get("sha256") is None,
                  f"{cid}: staged source digest cannot assert independent SHA-256 attestation")
        if isinstance(c.get("oracle"), dict):
            check(bool(c["oracle"].get("expectation")) and
                  bool(c["oracle"].get("source_refs")),
                  f"{cid}: oracle declaration missing")
        readbacks = (c.get("required_readback") or
                     (c.get("readback") or {}).get("required") or
                     (c.get("readback") or {}).get("missing") or
                     (c.get("readback") or {}).get("available") or
                     [s.get("server_observations") or s.get("authoritative_observations")
                      or s.get("observations_required") for s in steps])
        check(bool(readbacks) and (not isinstance(readbacks, list) or any(bool(x) for x in readbacks)),
              f"{cid}: missing readback")
        v2 = c.get("contract_v2")
        if v2 is not None:
            check(isinstance(v2, dict) and v2.get("contract_version") == 2,
                  f"{cid}: invalid optional v2 version")
            # Agent C's project_domain_case projection explicitly forbids
            # staged typed identity or normative-oracle authority. This is
            # NONCANONICAL metadata: never infer a v1 assertion or permission.
            check(not v2.get("parameters") and not v2.get("oracles"),
                  f"{cid}: staged v2 identity/oracle authority requires canonical review")
            requirements = v2.get("step_requirements", [])
            check(isinstance(requirements, list),
                  f"{cid}: v2 step requirements must be a bounded list")
            for req in requirements:
                check(isinstance(req, dict) and
                      req.get("execution_gate") == "blocked" and
                      req.get("step_id") in {s["id"] for s in steps} and
                      req.get("required_permissions") in (None, []) and
                      req.get("approval_required") is not False,
                      f"{cid}: invalid v2 gate, permission, or step")
        rows.append((cid, readiness))
    check(len(set(c for c, _ in rows)) == len(rows), f"{name}: duplicate IDs")
    return rows


def validate_snapshot(snapshot, manifest, catalog):
    check(manifest.get("execution_enabled") is False and
          len(manifest.get("domains", [])) == 9, "invalid manifest")
    rows = []
    for m in manifest["domains"]:
        check(re.fullmatch(r"[a-z_]+", m["name"]) is not None,
              "unsafe staging path")
        rows += validate_domain(m["name"], load(Path(snapshot) / (m["name"] + ".json")), m)
    check(len(rows) == manifest["expected_total"] == 73 and
          len({x[0] for x in rows}) == 73, "73 unique cases required")
    counts = Counter(x[1] for x in rows)
    check(dict(counts) == manifest["expected_lanes"], "readiness drift")
    check(sorted(x[0] for x in rows if x[1] == "observe-now") ==
          sorted(manifest["expected_observe_now"]), "unexpected observe-now expansion")
    check(catalog.get("schema_version") == 1 and
          isinstance(catalog.get("specifications"), list), "invalid v1 catalog")
    cases = catalog["specifications"]
    check({c.get("case_id") for c in cases} ==
          set(manifest["canonical_ids"]), "domain accidentally promoted to catalog")
    check([c.get("case_id") for c in cases if
           c.get("execution_status") == "verified_runner"] == ["MOG-09"],
          "unauthorized verified runner")
    return {"total": len(rows), "lanes": dict(counts), "executed": False,
            "source_attestation": "NOT_PERFORMED", "deployment": "UNKNOWN"}



def validate_reconciled_matrix(matrix, manifest, snapshot, observed_heads):
    """Compare the ONE proposed R5 matrix to exact staged PR JSON and fetched PR heads.

    Inputs are DATA ONLY. This does not import scenarios, execute actions, authenticate
    DSP file contents, or establish an installed server revision.
    """
    check(matrix.get("artifact_type") == "R5_domain_readiness_audit_not_canonical"
          and matrix.get("execution_enabled") is False
          and matrix.get("import_allowed") is False,
          "matrix: not the guarded, non-importable R5 readiness artifact")
    check(matrix.get("source", {}).get("principal_readiness_pr") == 1292,
          "matrix: PR #1292 is the proposed primary inventory (reconcile stale copy)")
    check(matrix.get("counts", {}).get("cases") == manifest["expected_total"]
          and matrix.get("counts", {}).get("lanes") == manifest["expected_lanes"],
          "matrix: 73-case lane summary differs from shared validation manifest")
    domains = manifest["domains"]
    refs = matrix.get("source", {}).get("domain_pr_head_snapshot")
    check(isinstance(refs, list) and len(refs) == len(domains),
          "matrix: missing nine exact staging PR head attestations (re-audit #1292)")
    pinned = {x.get("domain"): x for x in refs}
    check(len(pinned) == len(refs), "matrix: duplicate source domain head")
    check(isinstance(observed_heads, dict), "matrix: missing live Git PR HEAD snapshot")
    checks = {}
    for meta in domains:
        name = meta["name"]
        pin = pinned.get(name) or {}
        observed = observed_heads.get(name)
        check(pin.get("pr") == meta["pr"] and
              pin.get("source_revision") == meta["sha"] and
              pin.get("case_count") == meta["cases"],
              f"{name}: matrix source PR metadata stale; re-audit #1292")
        check(isinstance(pin.get("head_sha"), str)
              and SHA.fullmatch(pin["head_sha"]),
              f"{name}: malformed pinned staging PR head")
        check(observed == pin["head_sha"],
              f"{name}: STALE_SOURCE_PR_HEAD_REAUDIT_REQUIRED: "
              f"matrix pins {pin['head_sha']}, fetched {observed!r}")
        data = load(Path(snapshot) / (name + ".json"))
        checks.update({c["case_id"]: (name, meta["pr"], lane_of(c), c)
                       for c in data["cases"]})
    entries = matrix.get("cases")
    check(isinstance(entries, list) and len(entries) == len(checks)
          and len({c.get("scenario_id") for c in entries}) == len(entries),
          "matrix: duplicate, added or missing case IDs against nine staged JSON files")
    for record in entries:
        cid = record["scenario_id"]
        check(cid in checks, f"{cid}: absent in source staging PR; re-audit #1292")
        name, pr, lane, case = checks[cid]
        check(record.get("domain") == name and record.get("domain_pr") == pr
              and record.get("declared_lane") == lane
              and record.get("audited_lane") == lane,
              f"{cid}: MATRIX_LANE_OR_DOMAIN_DRIFT: expected {name} PR#{pr} {lane}")
        check(record.get("source_revision") ==
              (load_revision := pinned[name]["source_revision"]),
              f"{cid}: matrix DSP source revision differs from staged pinned SHA")
        expected = (case.get("oracle") or {}).get("expectation")
        if not expected:
            expected = "; ".join((case.get("behavior") or {}).get("then", []))
        if not expected:
            expected = "; ".join(a.get("expected", "")
                                 for a in case.get("assertions", []))
        expected = (expected or "UNKNOWN")[:900]
        check(record.get("expected_behavior") == expected,
              f"{cid}: EXPECTED_TEXT_CHANGED_REAUDIT_REQUIRED (do not auto-promote oracle)")
        live_refs = get_refs(case)
        record_refs = record.get("source_refs")
        check(isinstance(record_refs, list) and bool(record_refs),
              f"{cid}: matrix source refs missing")
        for r in record_refs:
            check(r.get("repository") == "sarthax/darkstar-to-valhalla"
                  and r.get("commit") == load_revision
                  and any(all(src.get(k) == r.get(k)
                              for k in ("repository", "commit", "path",
                                        "line_start", "line_end"))
                          for src in live_refs),
                  f"{cid}: MATRIX_PINNED_SOURCE_REF_DRIFT: cite staged line and SHA")
        check(record.get("runner_state") == "unassigned"
              and record.get("verdict") == "NOT_RUN_IN_THIS_AUDIT"
              and record.get("v2_import") == "BLOCKED_REVIEWED_MAPPER_REQUIRED",
              f"{cid}: imported or promoted readiness audit record")
        permissions = record.get("permissions")
        check(isinstance(permissions, list) and bool(permissions)
              and isinstance(record.get("blocking_gaps"), list)
              and (bool(record.get("readback_missing")) or
                   (lane == "observe-now" and bool(record.get("readback_available")))),
              f"{cid}: missing readback/permission or gap declaration")
        if lane == "needs-deploy":
            check(name == "chocobo_raising",
                  f"{cid}: deployed claim inconsistent with needs-deploy")
    return {"matrix": "CONSISTENT_WITH_PINNED_PR_HEADS",
            "cases": len(checks), "execution_enabled": False,
            "source_authenticity": "NOT_ATTESTED",
            "deployed_revision": "UNKNOWN"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-root", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--matrix", required=True, type=Path)
    p.add_argument("--observed-heads", required=True, type=Path)
    args = p.parse_args()
    manifest = load(args.manifest)
    base = validate_snapshot(args.snapshot_root, manifest, load(args.catalog))
    concord = validate_reconciled_matrix(load(args.matrix), manifest,
                                          args.snapshot_root, load(args.observed_heads))
    print(json.dumps({**base, **concord}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
