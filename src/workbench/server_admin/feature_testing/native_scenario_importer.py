"""#1410 slice 5: import native XiHeadless scenario JSON as DRAFT test-catalog revisions (offline, design-only).

Reads scenario files from a *pinned* revision of a local XiHeadless checkout with ``git`` (blobs at the pinned commit,
never the working tree, no network), reviews every step with ``typed_action_library.review_native_steps`` and, only
when every step of a scenario is SUPPORTED, adds a DRAFT revision through ``test_catalog.add_revision`` with source
``import:<repo>@<sha>:<path>``.

Fail closed: a scenario with any UNSUPPORTED / INVALID step is *rejected as a whole* and listed with the per-step
reasons; nothing is trimmed, translated or dropped to make it fit. Nothing here runs a scenario, assigns a runner,
approves an oracle, publishes, or touches a live server/client. The oracle is not reviewed: the stored placeholder
assertion is explicitly labelled as such and no verdict is assumed (A06 probes in particular stay annotations).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from . import test_catalog
from .typed_action_library import MAX_NATIVE_STEPS, review_native_steps

PINNED_REPO = "sarthax/xiheadless-dsp"
PINNED_SHA = "e5e80350711d5d2ec814c893a17c63baf3ef98a9"
FEATURE_ID = "native_xiheadless_import"  # a catalog namespace for imports, not a Toolkit feature
IMPORT_TAGS = ["native-import", "xiheadless"]
A06_MARK = "/A06-"
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")
_TOP = re.compile(r"scenarios/[^/]+\.json")
_EVIDENCE = re.compile(r"docs/evidence/.+/scenario\.json")
MAX_BLOB_BYTES = 65536


def _git(root: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False, timeout=60)
    if done.returncode != 0:
        raise ValueError("git %s failed: %s" % (args[0], done.stderr.decode("utf-8", "replace").strip()[:200]))
    return done.stdout


def resolve_pin(root: Path, sha: str) -> str:
    """Return the full commit id for ``sha`` in the local checkout, refusing anything that is not that exact commit."""
    if not _SHA40.fullmatch(sha):
        raise ValueError("the pinned revision must be a full 40-character lowercase commit sha")
    full = _git(root, "rev-parse", "--verify", sha + "^{commit}").decode().strip()
    if full != sha:
        raise ValueError("pinned revision does not resolve to itself")
    return full


def discover(root: Path, sha: str) -> list[str]:
    """Scenario file paths at the pinned commit: ``scenarios/*.json`` and ``docs/evidence/**/scenario.json``."""
    names = _git(root, "ls-tree", "-r", "--name-only", sha).decode("utf-8").splitlines()
    return sorted(n for n in names if _TOP.fullmatch(n) or _EVIDENCE.fullmatch(n))


def read_blob(root: Path, sha: str, path: str) -> bytes:
    data = _git(root, "cat-file", "blob", f"{sha}:{path}")
    if len(data) > MAX_BLOB_BYTES:
        raise ValueError("scenario file larger than %d bytes" % MAX_BLOB_BYTES)
    return data


def case_id_for(path: str) -> str:
    stem = str(PurePosixPath(path).with_suffix(""))
    return _SAFE.sub("-", stem).strip("-")[:120]


def _canonical_sha(steps: object) -> str:
    return hashlib.sha256(json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _shape(steps: list) -> str:
    """Action/check key sequence only (values and names ignored): used to *report* near-duplicates, never to merge."""
    def keys(part: object) -> str:
        return "+".join(sorted(part)) if isinstance(part, dict) else "?"
    return " > ".join(f"{keys(s.get('do'))}|{keys(s.get('expect'))}" if isinstance(s, dict) else "?" for s in steps)


def _review(steps: list) -> tuple[dict, list]:
    """Review ``steps`` as they are; per-step ``timeout_ms`` is a permitted native_steps field and is kept."""
    return review_native_steps(steps), steps


def _build_spec(path: str, sha: str, repo: str, steps: list, reviewed: list, aliases: list[str]) -> dict:
    short = sha[:8]
    stored = []
    for index, (orig, step) in enumerate(zip(steps, reviewed), 1):
        note = f"{PurePosixPath(path).name}@{short} step {index}/{len(steps)}"
        stored.append({**step, "note": note[:300]})
    gaps = [
        "Imported from %s@%s:%s. Source identity only: not an approved oracle, not authenticated, not run." % (repo, short, path),
        "Placeholder assertion 'oracle_unreviewed' only satisfies the spec shape; the real expected outcome is the "
        "native expect map in each step and has no approved oracle or verdict (UNKNOWN).",
        "OWNER QUESTION (open): is this scenario a wanted catalog case, and under which feature/case id and tags?",
    ]
    if A06_MARK in "/" + path:
        gaps.append("A06 acceptance probe path: the source set includes expected-failure / fault-injection probes. Polarity "
                    "(pass-expected vs fail-expected) is NOT classified; no verdict is assumed. OWNER QUESTION (open).")
    if aliases:
        gaps.append(("Exact duplicate content (identical step array incl. names, values and timeouts) found at: "
                     + ", ".join(aliases))[:500])
    spec = {
        "schema_version": 1, "feature_id": FEATURE_ID, "case_id": case_id_for(path),
        "name": ("Native scenario " + path)[:120],
        "purpose": ("DRAFT import of a native XiHeadless scenario file, kept only so a reviewer can read it. Nothing is run "
                    "and no outcome is asserted."),
        "runner": "unassigned", "execution_status": "design_only",
        "preconditions": [f"Source file {path} at {repo}@{short}", "Any later run needs separate owner approval (#1412)"],
        "observations": ["session"],
        "assertions": [{"id": "oracle_unreviewed", "operation": "nonempty", "observed": "session", "expected": None}],
        "cleanup": ["Design only; the catalog never executes this"],
        "authoring": {"state": "IMPORTED_DRAFT_UNREVIEWED", "execution_policy": "none: design_only, runner unassigned",
                      "evidence_provenance": f"import:{repo}@{short}:{path}"[:160], "blocking_gaps": gaps,
                      "review_required": True},
        "native_steps": {"library_version": 1, "steps": stored},
    }
    return spec


def run_import(root: Path, *, sha: str = PINNED_SHA, repo: str = PINNED_REPO, carry_timeouts: bool = False,
               apply: bool = True) -> dict:
    """Import every discovered scenario. ``apply=False`` reviews and reports but writes nothing."""
    sha = resolve_pin(root, sha)
    paths = discover(root, sha)
    report = {"schema": "toolkit-native-import-report/1", "source": {"repo": repo, "sha": sha, "files_examined": len(paths)},
              "carry_step_timeouts": True, "applied": apply, "imported": [], "unchanged": [], "rejected": [],
              "deduplicated": [], "near_duplicate_shapes": []}
    parsed: dict[str, list] = {}
    for path in paths:
        try:
            value = json.loads(read_blob(root, sha, path).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            report["rejected"].append({"path": path, "reason": "unreadable or not JSON: %s" % str(exc)[:150], "steps": []})
            continue
        if not isinstance(value, list) or not 1 <= len(value) <= MAX_NATIVE_STEPS:
            report["rejected"].append({"path": path, "reason": f"root must be an array of 1 to {MAX_NATIVE_STEPS} steps",
                                       "steps": []})
            continue
        parsed[path] = value
    groups: dict[str, list[str]] = {}
    for path, steps in parsed.items():
        groups.setdefault(_canonical_sha(steps), []).append(path)
    shapes: dict[str, list[str]] = {}
    seen_ids: dict[str, str] = {}
    for digest, members in sorted(groups.items(), key=lambda kv: sorted(kv[1])[0]):
        members.sort()
        primary, aliases = members[0], members[1:]
        steps = parsed[primary]
        if aliases:
            report["deduplicated"].append({"kept": primary, "merged_exact_duplicates": aliases, "content_sha256": digest,
                                           "reason": "identical parsed step array (names, values, timeouts); kept the "
                                                     "first path in sort order and recorded the others in the draft"})
        review, reviewed = _review(steps)
        bad = [{"index": r["index"], "name": r["name"], "status": r["status"], "reasons": r["reasons"]}
               for r in review["steps"] if r["status"] != "SUPPORTED"]
        if bad:
            report["rejected"].append({"path": primary, "also_at": aliases, "reason": "%d of %d step(s) not SUPPORTED by the "
                                       "typed library; scenario not imported" % (len(bad), len(steps)), "steps": bad})
            continue
        case = case_id_for(primary)
        if case in seen_ids:
            report["rejected"].append({"path": primary, "reason": f"case id {case!r} collides with {seen_ids[case]}", "steps": []})
            continue
        seen_ids[case] = primary
        shapes.setdefault(_shape(steps), []).append(primary)
        try:
            spec = _build_spec(primary, sha, repo, steps, reviewed, aliases)
            test_catalog._check_spec(spec)
            if len(names := [s["name"] for s in steps]) != len(set(names)):
                raise ValueError("duplicate step names")
        except (ValueError, KeyError, TypeError) as exc:
            report["rejected"].append({"path": primary, "also_at": aliases, "steps": [],
                                       "reason": "reviewed steps cannot be stored as a valid draft: %s" % str(exc)[:200]})
            continue
        source = f"import:{repo}@{sha}:{primary}"
        item = {"path": primary, "feature_id": FEATURE_ID, "case_id": case, "source": source,
                "tags": IMPORT_TAGS + (["a06-probe"] if A06_MARK in "/" + primary else [])}
        if not apply:
            report["imported"].append({**item, "revision": None, "dry_run": True})
            continue
        existing = test_catalog.get_entry(FEATURE_ID, case)
        serialized = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        latest = existing["revisions"][-1] if existing else None
        if latest and latest["content_sha256"] == hashlib.sha256(serialized.encode("utf-8")).hexdigest():
            report["unchanged"].append({**item, "revision": latest["revision"]})
            continue
        out = test_catalog.add_revision(spec, source=source, tags=item["tags"],
                                        expected_latest=latest["revision"] if latest else 0)
        report["imported"].append({**item, "revision": out["revision"], "state": out["state"]})
    report["near_duplicate_shapes"] = [{"shape": shape, "paths": sorted(p), "note": "same action/check key sequence, different "
                                        "values or names; NOT merged, owner decides"}
                                       for shape, p in shapes.items() if len(p) > 1]
    report["counts"] = {"files_examined": len(paths), "distinct_contents": len(groups), "imported": len(report["imported"]),
                        "unchanged": len(report["unchanged"]), "rejected_scenarios": len(report["rejected"]),
                        "exact_duplicate_files_merged": sum(len(d["merged_exact_duplicates"]) for d in report["deduplicated"])}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", required=True, type=Path, help="local XiHeadless git checkout (read with git, no network)")
    ap.add_argument("--sha", default=PINNED_SHA)
    ap.add_argument("--repo", default=PINNED_REPO)
    ap.add_argument("--scratch-db", required=True, type=Path, help="NEW sqlite file to write drafts into (absolute path)")
    ap.add_argument("--allow-existing-db", action="store_true", help="append to an existing scratch db (still never the live data)")
    ap.add_argument("--carry-step-timeouts", action="store_true",
                    help="deprecated no-op: per-step timeout_ms is always carried unchanged now")
    ap.add_argument("--dry-run", action="store_true", help="review and report only; write nothing")
    ap.add_argument("--report", type=Path, help="write the JSON report here")
    args = ap.parse_args(argv)
    db = args.scratch_db
    if not db.is_absolute() or not db.parent.is_dir():
        ap.error("--scratch-db must be an absolute path whose folder exists")
    if db.exists() and not args.allow_existing_db:
        ap.error("--scratch-db already exists; pass a new file (or --allow-existing-db for a scratch copy)")
    if "MISSION_TOOLKIT_TEST_DRAFTS_DB" in os.environ and Path(os.environ["MISSION_TOOLKIT_TEST_DRAFTS_DB"]).resolve() == db.resolve():
        ap.error("--scratch-db must not be the Toolkit's configured drafts database")
    os.environ["MISSION_TOOLKIT_TEST_DRAFTS_DB"] = str(db)  # this process only
    report = run_import(args.source_root, sha=args.sha, repo=args.repo, carry_timeouts=args.carry_step_timeouts,
                        apply=not args.dry_run)
    text = json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "source": report["source"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
