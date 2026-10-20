# Ready watch (issue discovery / conflict report)

Workflow `.github/workflows/ready-watch.yml`, script `.github/scripts/ready_watch.py` (identical in all three repos).

## What it does
When an issue gets or loses the `ready` label (or a ready issue is edited/reopened) it keeps ONE comment on the issue
(marker `<!-- ready-watch -->`) saying:
- **eligible** or **needs coordinator attention**
- Files owned, Depends on, acceptance-criteria count
- missing spec: empty `Files owned` / `Acceptance criteria` (blocks); empty `Do not touch` (warning)
- ownership overlap with other open `ready` issues and with open PRs (exact path, directory prefix or glob); the
  other ready issue's comment is refreshed too so both sides show the overlap

The comment is rewritten only when its content hash changes, so unchanged state is never re-announced. GitHub emails
you on a new comment on issues you watch. Removing `ready` rewrites the comment as "no longer ready".

## Safety
Read-only except for that one comment (permissions: contents read, issues write, pull-requests read; built-in
`GITHUB_TOKEN`, no PATs or third-party services). It never changes labels, assignments or branches and never starts
a worker. Issue text is parsed as data and echoed only in code spans; API errors fail the run (red X), never "empty".

## Transition (unchanged; this adds step 1-2 visibility)
`ready` -> coordinator reviews the watch comment -> worker claims (`in-progress`) -> PR `needs-local-test`
-> Claude local test -> `tested-ok` / `failed`. A worker must not claim an issue whose watch comment shows an overlap or
missing spec; fix the issue first.

## Inspect the queue
`gh issue list --label ready --state open` and open each comment, or Actions tab -> `ready-watch` runs.

## Test
Offline: `python3 .github/scripts/test_ready_watch.py`. Live: create an issue from the worker-task template, add `ready`,
see the comment; add a second ready issue owning the same path and see both flagged; remove `ready`.

## Pause / disable
Actions tab -> `ready-watch` -> "..." -> Disable workflow (or `gh workflow disable ready-watch`).

## Limits
- Event-only (no cron): an issue whose label was set while Actions was disabled is not reported until edited.
- Tokens are per-repo; cross-repo dependencies (`owner/repo#N`) are listed, not resolved.
- PR file lists are capped at 300 files each.
- It does not launch ChatGPT. The hourly ChatGPT "FFXI Ready Issue Watch" is independent and complements this by
  reconciling missed events; hand-off from either to a worker is still manual.
