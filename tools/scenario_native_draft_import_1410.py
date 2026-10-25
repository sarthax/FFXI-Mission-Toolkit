#!/usr/bin/env python3
"""Offline, fail-closed XIHeadless native JSON -> UNTRUSTED draft preview.
Never imports into Toolkit databases, publishes, or executes anything.
"""
import argparse
import hashlib
import json
from pathlib import Path

PIN = "159a5b9d4b4e43397bd509a816a7241a97511319"
# Deliberately narrow source-read subset: known keys are NOT runtime support guarantees.
ACTIONS = {"walk_to", "talk_npc", "examine_npc", "event_update", "event_finish", "wait_ms", "engage", "invite", "accept_invite", "rest_hp"}
EXPECTATIONS = {"zone", "hpp", "event_active", "event_id", "entities_gt", "party_members_gt", "x_near"}
MAX_BYTES = 1024 * 1024

def preview(raw: bytes, *, source_path: str, source_sha: str, repo_sha: str = PIN, expected_failure: bool = False):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("missing or oversized native JSON bytes")
    if not source_path or source_path.startswith("/") or ".." in Path(source_path).parts or "\\" in source_path:
        raise ValueError("missing/unsafe source path")
    if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise ValueError("source_sha must be verified 64-character lowercase SHA-256")
    if hashlib.sha256(raw).hexdigest() != source_sha:
        raise ValueError("source digest mismatch")
    if repo_sha != PIN:
        raise ValueError("unreviewed source repository revision")
    try:
        steps = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(steps, list) or not steps:
        raise ValueError("native scenario must be a nonempty array")
    seen = set()
    rows = []
    blockers = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"].strip():
            raise ValueError(f"step {idx}: missing name")
        name = step["name"].strip()
        if name in seen:
            raise ValueError(f"step {idx}: duplicate step identity")
        seen.add(name)
        if "do" in step and not isinstance(step["do"], dict):
            raise ValueError(f"step {idx}: do must be object")
        if "expect" in step and not isinstance(step["expect"], dict):
            raise ValueError(f"step {idx}: expect must be object")
        if not isinstance(step.get("timeout_ms", 1), int) or isinstance(step.get("timeout_ms", 1), bool) or not 1 <= step.get("timeout_ms", 1) <= 3600000:
            raise ValueError(f"step {idx}: invalid timeout_ms")
        actions = step.get("do", {})
        expects = step.get("expect", {})
        unknown_actions = sorted(set(actions) - ACTIONS)
        unknown_expectations = sorted(set(expects) - EXPECTATIONS)
        for k in unknown_actions:
            blockers.append(f"step {idx}: unsupported/unreviewed action {k}")
        for k in unknown_expectations:
            blockers.append(f"step {idx}: unsupported/unreviewed expectation {k}")
        if not expects:
            blockers.append(f"step {idx}: no approved oracle")
        # Shape-level check only; no native schema execution guarantee.
        for k, v in expects.items():
            if v is None or isinstance(v, (list, dict)):
                blockers.append(f"step {idx}: unreviewed expectation shape {k}")
        rows.append({"order": idx + 1, "human_description": name, "native_action_keys": sorted(actions),
                     "native_expectation_keys": sorted(expects), "native_do_untrusted": actions,
                     "native_expect_untrusted": expects, "support": "UNVERIFIED",
                     "oracle_review_state": "UNAPPROVED", "verdict": "UNKNOWN"})
    if "A06" in source_path.upper() and not expected_failure:
        blockers.append("A06 fault-injection classification requires owner review")
    if expected_failure:
        blockers.append("expected-failure/fault-injection classification is source annotation only, not verified oracle")
    # Even fully shape-recognized inputs are untrusted draft only.
    return {"schema": "toolkit-native-draft-preview/1", "status": "DRAFT_ONLY",
            "admission": "BLOCKED", "execution_enabled": False, "publish_enabled": False,
            "source": {"repository": "sarthax/xiheadless-dsp", "repository_sha": repo_sha,
                       "path": source_path, "content_sha256": source_sha,
                       "identity_trust": "UNVERIFIED_EXTERNAL_SOURCE"},
            "candidate_id": "untrusted:" + source_sha[:20], "expected_failure_claim": expected_failure,
            "steps": rows, "blockers": blockers + ["independent oracle and owner selection not approved"],
            "original_verdict": None, "independent_oracle_verdict": "UNKNOWN"}

def inventory(files, *, source_root: Path, expected_fail_paths=()):
    results = []
    for file in sorted(files):
        try:
            relative = file.relative_to(source_root).as_posix()
            raw = file.read_bytes()
            result = preview(raw, source_path=relative, source_sha=hashlib.sha256(raw).hexdigest(),
                             expected_failure=any(x in relative for x in expected_fail_paths))
            results.append({"path": relative, "result": result})
        except (ValueError, OSError) as exc:
            results.append({"path": str(file), "status": "BLOCKED", "reason": str(exc)})
    return {"inventory_status": "OFFLINE_UNTRUSTED", "source_pin": PIN,
            "source_files_examined": len(results),
            "candidate_previews": sum("result" in x for x in results),
            "entries": results}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="Directory of separately acquired native .json scenario files; never writes to it")
    ap.add_argument("--expected-fail-path", action="append", default=[])
    args = ap.parse_args()
    if not args.root.is_dir():
        ap.error("source directory is missing")
    print(json.dumps(inventory(args.root.rglob("*.json"), source_root=args.root,
                               expected_fail_paths=args.expected_fail_path), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
