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
        asserted = {a["id"] for a in c.get("assertions", [])}
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
                  s.get("manual_execution_allowed") is not True,
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
            check(str(ref.get("url", "")).startswith(
                  "https://github.com/sarthax/darkstar-to-valhalla/blob/"
                  + revision + "/" + path + "#L" + str(start)),
                  f"{cid}: unpinned URL")
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
        check(bool(readbacks), f"{cid}: missing readback")
        v2 = c.get("contract_v2")
        if v2 is not None:
            check(isinstance(v2, dict) and v2.get("contract_version") == 2,
                  f"{cid}: invalid optional v2 version")
            for req in v2.get("step_requirements", []):
                check(req.get("execution_gate") == "blocked" and
                      req.get("step_id") in {s["id"] for s in steps},
                      f"{cid}: invalid v2 execution gate/step")
            for oracle in v2.get("oracles", []):
                check(oracle.get("oracle_type") != "unknown" or
                      (oracle.get("confidence") == "unknown" and
                       not oracle.get("source_refs")),
                      f"{cid}: unknown v2 oracle has source claim")
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-root", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--catalog", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(validate_snapshot(args.snapshot_root, load(args.manifest),
                                       load(args.catalog)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
