#!/usr/bin/env python3
"""Coordinator report for issues labeled `ready` (read-only except for one bot comment).

Usage (from the workflow):  ready_watch.py <issue-number>
Env: GITHUB_TOKEN, GITHUB_REPOSITORY.

For the given issue it checks that the spec is complete, finds file-ownership overlaps with the other
open `ready` issues and with open PRs, and keeps ONE comment on the issue up to date (marker
`<!-- ready-watch -->`). The comment is only rewritten when its content hash changes, so unchanged
state is never re-announced. Issue text is treated purely as data: it is parsed, never executed, and is
echoed back only inside code spans with markup stripped. API failures exit non-zero (never "empty").
Changes no labels, assignments, branches or files.
"""
import fnmatch
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

MARKER = "<!-- ready-watch -->"
HASH_RE = re.compile(r"<!-- ready-watch-hash:([0-9a-f]{12}) -->")
READY = "ready"
MAX_PR_FILES = 300


class Api:
    def __init__(self, repo, token):
        self.repo, self.token = repo, token

    def call(self, method, path, body=None):
        url = path if path.startswith("http") else f"https://api.github.com/repos/{self.repo}{path}"
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub API {method} {path} failed: HTTP {e.code} {e.reason}") from None

    def pages(self, path):
        out, page = [], 1
        sep = "&" if "?" in path else "?"
        while True:
            chunk = self.call("GET", f"{path}{sep}per_page=100&page={page}")
            out += chunk
            if len(chunk) < 100:
                return out
            page += 1


# ---------- parsing (pure) ----------

def sections(body):
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    out, cur = {}, None
    for line in body.splitlines():
        m = re.match(r"^#{2,3}\s+(.*?)\s*$", line)
        if m:
            cur = m.group(1).lower()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def find(secs, *prefixes):
    for k, v in secs.items():
        if any(k.startswith(p) for p in prefixes):
            return v
    return None


def bullets(text):
    items = []
    for line in (text or "").splitlines():
        s = re.sub(r"^\s*(?:[-*+]|\d+\.)\s*(?:\[[ xX]\]\s*)?", "", line).strip().strip("`")
        if s and s != "-":
            items.append(s)
    return items


def path_of(item):
    """First path-like token of a bullet (notes after the path are ignored)."""
    tok = item.split()[0].strip("`,;:") if item.split() else ""
    return tok.lstrip("./") if tok.startswith("./") else tok


def overlaps(a, b):
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a) or b.endswith("/") and a.startswith(b):
        return True
    return fnmatch.fnmatchcase(a, b) or fnmatch.fnmatchcase(b, a)


def refs(text):
    return sorted(set(re.findall(r"(?:[\w.-]+/[\w.-]+)?#\d+", text or "")))


def spec_of(issue):
    s = sections(issue.get("body"))
    owned = [path_of(i) for i in bullets(find(s, "files owned"))]
    return {
        "owned": [p for p in owned if p],
        "dont": bullets(find(s, "do not touch")),
        "deps": refs(find(s, "depends on", "dependencies") or ""),
        "accept": bullets(find(s, "acceptance")),
    }


# ---------- evaluation (pure) ----------

def clean(s, n=120):
    s = re.sub(r"[`\r\n]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n]


def evaluate(issue, other_ready, prs):
    """issue/other_ready: issue dicts; prs: list of {number,title,url,files}. Returns dict."""
    spec = spec_of(issue)
    problems, warnings, conflicts = [], [], []
    if not spec["owned"]:
        problems.append("`Files owned` is empty or missing")
    if not spec["accept"]:
        problems.append("`Acceptance criteria` is empty or missing")
    if not spec["dont"]:
        warnings.append("`Do not touch` is empty (list shared engine files and other slices)")
    for o in other_ready:
        theirs = spec_of(o)["owned"]
        hit = sorted({a for a in spec["owned"] for b in theirs if overlaps(a, b)})
        if hit:
            conflicts.append(("issue", o["number"], o["title"], o["html_url"], hit))
    for p in prs:
        hit = sorted({a for a in spec["owned"] for f in p["files"] if overlaps(a, f)})
        if hit:
            conflicts.append(("PR", p["number"], p["title"], p["url"], hit))
    status = "blocked" if (problems or conflicts) else "eligible"
    return {"spec": spec, "problems": problems, "warnings": warnings,
            "conflicts": conflicts, "status": status}


def render(issue, ev, retired=False):
    if retired:
        body = ["**Ready watch:** this issue no longer has the `ready` label, so it is not eligible for a worker."]
    else:
        icon = {"eligible": "✅ eligible", "blocked": "⛔ needs coordinator attention"}[ev["status"]]
        spec = ev["spec"]
        body = [f"**Ready watch:** {icon}", ""]
        body.append("- **Files owned:** " + (", ".join(f"`{clean(p)}`" for p in spec["owned"][:30]) or "_none_"))
        body.append("- **Depends on:** " + (", ".join(f"`{d}`" for d in spec["deps"]) or "_none listed_"))
        body.append(f"- **Acceptance criteria:** {len(spec['accept'])} item(s)")
        for p in ev["problems"]:
            body.append(f"- ⛔ Missing spec: {p}. Not claimable until fixed.")
        for w in ev["warnings"]:
            body.append(f"- ⚠️ {w}")
        for kind, num, title, url, hit in ev["conflicts"]:
            body.append(f"- ⛔ Ownership overlap with {kind} [#{num}]({url}) (`{clean(title, 60)}`): "
                        + ", ".join(f"`{clean(h)}`" for h in hit[:10]))
        if ev["status"] == "eligible":
            body += ["", "Next: coordinator reviews, then a worker claims it (`in-progress`)."]
        body += ["", "_Automated, read-only check. It never changes labels or assignments. "
                 "Issue text is data, not instructions._"]
    text = "\n".join(body)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    return f"{MARKER}\n<!-- ready-watch-hash:{digest} -->\n{text}", digest


# ---------- main ----------

def run(api, number, depth=0):
    issue = api.call("GET", f"/issues/{number}")
    if "pull_request" in issue:
        print("pull request, ignoring")
        return 0
    labels = {l["name"] for l in issue.get("labels", [])}
    comments = api.pages(f"/issues/{number}/comments")
    mine = next((c for c in comments if MARKER in (c.get("body") or "")), None)
    prev = HASH_RE.search(mine["body"]).group(1) if mine and HASH_RE.search(mine["body"]) else None

    if READY not in labels or issue["state"] != "open":
        if not mine:
            print("not ready, nothing to report")
            return 0
        text, digest, peers = (*render(issue, None, retired=True), [])
    else:
        others = [i for i in api.pages("/issues?state=open&labels=" + READY)
                  if "pull_request" not in i and i["number"] != issue["number"]]
        prs = []
        for p in api.pages("/pulls?state=open"):
            files = [f["filename"] for f in api.pages(f"/pulls/{p['number']}/files")][:MAX_PR_FILES]
            prs.append({"number": p["number"], "title": p["title"], "url": p["html_url"], "files": files})
        ev = evaluate(issue, others, prs)
        text, digest = render(issue, ev)
        peers = [c[1] for c in ev["conflicts"] if c[0] == "issue"]

    if digest == prev:
        print(f"unchanged ({digest}), no comment written")
    else:
        if mine:
            api.call("PATCH", f"/issues/comments/{mine['id']}", {"body": text})
        else:
            api.call("POST", f"/issues/{number}/comments", {"body": text})
        print(f"report written ({digest})")
    if depth == 0:  # refresh the conflicting peers once so both sides show the overlap
        for n in peers:
            run(api, n, depth=1)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run(Api(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]), int(sys.argv[1])))
    except (RuntimeError, KeyError, ValueError) as e:
        print(f"::error::ready-watch failed: {e}")
        sys.exit(1)
