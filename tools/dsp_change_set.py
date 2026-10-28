"""Write an R6 change-set JSON between two DSP revisions (design: docs/workbench/R6_REGRESSION_IMPACT_DESIGN_1199_1210.md).

Run on the operator's machine against a local DSP checkout. The only git commands used are read-only
(rev-parse, status, diff); the checkout is never modified and nothing touches the network. The output is
validated by ``workbench.server_admin.feature_testing.impact_changeset.validate_change_set`` (tests assert
that every file this script writes passes it).

    python tools/dsp_change_set.py --repo-path D:\\dsp --repository owner/repo \\
        --base <ref> --head <ref> --output change_set.json
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

MAX_CHANGES = 5000
MAX_HUNKS_PER_CHANGE = 2000
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


class ChangeSetError(RuntimeError):
    pass


def _git(repo, *args):
    # Argument list, never a shell string; refs/paths cannot be interpreted as shell syntax.
    proc = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
                          capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ChangeSetError(f"git {args[0]} failed: {detail[-1] if detail else 'no output'}")
    return proc.stdout


def resolve(repo, ref):
    out = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    sha = out.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ChangeSetError(f"{ref!r} did not resolve to a full commit SHA")
    return sha


def check_checkout(repo):
    if not Path(repo).is_dir():
        raise ChangeSetError(f"not a directory: {repo}")
    if _git(repo, "rev-parse", "--is-shallow-repository").decode().strip() == "true":
        raise ChangeSetError("refusing a shallow checkout: the diff between the revisions may be incomplete")
    if _git(repo, "status", "--porcelain").strip():
        raise ChangeSetError("refusing a checkout with uncommitted changes; use a clean checkout")


def name_status(repo, base, head):
    """Parse ``git diff --name-status -M -z`` into (status, path, old_path) tuples."""
    raw = _git(repo, "diff", "--name-status", "-M", "-z", "--no-ext-diff", base, head).split(b"\0")
    fields = [f.decode("utf-8", "surrogateescape") for f in raw if f != b""]
    rows, i = [], 0
    while i < len(fields):
        code = fields[i]
        kind = code[0]
        if kind in "AMD":
            rows.append((kind, fields[i + 1], None))
            i += 2
        elif kind == "R":
            rows.append(("R", fields[i + 2], fields[i + 1]))
            i += 3
        else:
            raise ChangeSetError(f"unsupported git status {code!r} for {fields[i + 1]!r}; "
                                 "typechanges, copies and unmerged paths are not supported")
    return rows


def base_hunks(repo, base, head, path, old_path):
    """Base-side line ranges for one file (None when git reports no textual hunks, e.g. binary).

    A pure insertion has no base lines, so it is recorded as the base line it follows
    (1 at the start of a file): this over-selects a neighbour rather than missing it.
    """
    specs = [f":(literal){p}" for p in ((old_path, path) if old_path else (path,))]
    text = _git(repo, "diff", "--unified=0", "--no-color", "--no-ext-diff", "-M",
                base, head, "--", *specs).decode("utf-8", "replace")
    ranges = []
    for line in text.splitlines():
        match = _HUNK.match(line)
        if not match:
            continue
        start, count = int(match.group(1)), int(match.group(2) or 1)
        if count == 0:
            line_no = max(start, 1)
            ranges.append([line_no, line_no])
        else:
            ranges.append([start, start + count - 1])
    if len(ranges) > MAX_HUNKS_PER_CHANGE:
        raise ChangeSetError(f"{path!r} has more than {MAX_HUNKS_PER_CHANGE} hunks")
    # Merge touching/overlapping ranges so the list is ordered and non-overlapping.
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged or None


def build(repo, repository, base_ref, head_ref):
    check_checkout(repo)
    base, head = resolve(repo, base_ref), resolve(repo, head_ref)
    if base == head:
        raise ChangeSetError("base and head resolve to the same commit")
    rows = name_status(repo, base, head)
    if len(rows) > MAX_CHANGES:
        raise ChangeSetError(f"{len(rows)} changed paths exceeds the limit of {MAX_CHANGES}")
    changes = []
    for status, path, old_path in rows:
        hunks = None if status in "AD" else base_hunks(repo, base, head, path, old_path)
        changes.append({"status": status, "path": path, "old_path": old_path, "hunks": hunks})
    return {"schema_version": 1, "repository": repository, "base_sha": base, "head_sha": head,
            "changes": changes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo-path", required=True, help="local DSP checkout (read-only use)")
    parser.add_argument("--repository", required=True,
                        help="repository name exactly as written in scenario contract_v2 sources")
    parser.add_argument("--base", required=True, help="base revision (branch, tag or SHA)")
    parser.add_argument("--head", required=True, help="head revision (branch, tag or SHA)")
    parser.add_argument("--output", required=True, help="JSON file to write (must not already exist)")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        print(f"refusing to overwrite existing file: {output}", file=sys.stderr)
        return 2
    try:
        document = build(args.repo_path, args.repository, args.base, args.head)
    except ChangeSetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(document['changes'])} change(s) {document['base_sha'][:12]}..{document['head_sha'][:12]} to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
