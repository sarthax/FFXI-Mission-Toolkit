# FFXI autonomous worker pipeline

Implementation scope: Toolkit issue #1178. Claude Code/owner retains live testing, final review and merging.
No changes to existing watchers, repository rules, CI permissions, accounts or game systems.

## Verified audit (2026-10-20 UTC)

Read all three repositories' AGENTS.md and xiheadless-dsp/CLAUDE.md before implementation.

| Component | Actual behavior |
| --- | --- |
| Hourly ChatGPT task, FFXI Ready Issue Watch | Enabled; prompt explicitly prohibits claims, label changes, branches, PRs and repository modifications. Discovery/reporting only. Its last observed run was 2026-10-20T03:22:28Z. |
| `.github/workflows/ready-watch.yml` in all three repos | On issue label/edit/reopen events, runs offline watcher tests then updates one eligibility comment. No execution job. |
| `.github/scripts/ready_watch.py` | Parses ownership/acceptance/dependency references and reports ready-peer/PR conflicts. Reports dependencies but does not resolve their completion. Existing parser reused by dispatcher; existing files untouched. |
| Available GitHub connector | Reads/writes issues, Git objects, branches and PRs; reads Actions runs and can rerun existing jobs. No exposed workflow-dispatch or remote coding-agent launch tool in this session. Comments/assignments are not agent launches. |
| ChatGPT Work session collaboration | An actual subagent can be launched during this authorized session. Demonstrated on xiheadless-dsp #57. This is not a callable persistent external worker service or proof that scheduled tasks expose the same runtime. |
| Supported external execution | Official `codex exec` CLI runs noninteractive jobs with workspace-write sandbox and machine-readable output. Adapter implemented using an isolated container; deployed/authenticated execution remains unverified here. |

Open PRs at initial audit: xiheadless #7/#8 (parent work), #58 (backlog docs), #59 (chocobo diagnostics);
Toolkit #1157 and #1170–#1177; DSP #51. PR file lists were inspected for ownership collisions.
Latest sampled Actions showed successful ready-watch and .NET runs in xiheadless, successful worker-gates
for DSP #51, and successful Workbench/Src Layout runs in Toolkit. These are samples, not acceptance of every PR.

Candidate #57 was ready, unassigned, main-based, dependency-free, remote-safe, and had no PR/file overlap.
Candidate #50 had the same eligibility properties with distinct owned files. Its existing char_pool.py
already waits with a timeout and cooldown; FIFO tickets/fairness are the remaining proposed work.
Do not reimplement its existing timeout, alter the allowlist or run/provision real accounts.
Other ready issues override main with child bases under #7/#8; dispatcher reads that explicit base.
No currently ready worker issues were found in the other two repos before #1178 was created.

Official execution reference: https://learn.chatgpt.com/docs/non-interactive-mode

## Architecture and trust boundary

The Toolkit contains the shared controller (`tools/autonomous_worker/`). One SQLite database on durable
local disk is the sole authority across all three repositories. SQLite `BEGIN IMMEDIATE` serializes
claim, capacity and ownership decisions. All controller instances must use this same DB and concurrency
setting. Never put SQLite/WAL on NFS or copy it into separate active replicas. Use one supervised service
instance for discovery/outbox delivery; worker threads have their own DB connections.

This guarantees atomic claims among cooperating controller workers. GitHub labels/comments do not offer
compare-and-swap ownership and cannot exclude independent manual/Claude workers. Before deployment,
Claude and every manual worker must use/respect the central queue and its in-progress labels; pause
independent dispatchers. Fresh GitHub checks narrow external races but cannot make external actors transactional.
This limit must not be described as a GitHub-wide atomic lock.

Discovery is paginated and fail-closed: API errors are not an empty queue. It requires ready + remote-safe/hybrid,
open/unassigned, explicit ownership/acceptance/exclusions/dependencies/base, completed dependencies,
no overlap with other ready/in-progress issues or open PRs, including renamed filenames. PR truncation blocks.
Unknown dependencies/base/specs require coordinator attention. The parser reuses the existing watcher;
globs lock their static parent conservatively (two complex globs must never silently miss a collision).
Publication accepts exact files or owned directory prefixes; glob scopes need coordinator expansion first.

Ready alone is insufficient to execute: `approved_issues` pins each authorized issue body SHA256 returned by
`discover`. This is a reviewed scope approval, not an arbitrary command from issue text. Changed text needs
fresh approval. Configured test argv arrays are controller policy, never shell snippets supplied by an issue.
The coordinator approves the parent branch where required. Missing test policy blocks execution.

## Durable lifecycle

| State | Worker slot | File lock | Next action |
| --- | --- | --- | --- |
| queued | no | no | Fresh GitHub check, matching approval, atomic claim |
| claimed/running | yes | yes | Supervisor heartbeat every ~15 seconds; bounded offline work |
| retry_wait | no | yes | Exponential backoff, only after confirmed process/container termination; max three attempts |
| uncertain | yes | yes | Coordinator proves worker stopped and checks publication; never auto-retry |
| awaiting_review | no | yes | Draft PR needs-local-test; Claude reviews/tests/merges |
| failed | no | no DB lock | Attempts exhausted; GitHub in-progress marker remains until coordinator reconciliation |
| resolved | no | no | Explicit coordinator disposition recorded |

The default AND hard maximum is three concurrent workers across repositories; configurable 1..3.
Capacity is persisted; inconsistent controllers fail rather than applying conflicting settings. To change it,
stop the service, resolve/drain active jobs, update the settings row and config together, then restart.
The worker timeout defaults to 1800 seconds. Heartbeat expiry defaults to 180 seconds and fences the old
lease token. A dead controller may leave a container alive: uncertainty keeps its slot/locks until inspected.
Container names use the `ffxi-worker-` prefix; inspect the dedicated Docker daemon during recovery.

Job/spec/attempt/token/heartbeat/detail, event history and notification outbox survive restart on the configured
durable volume. Tokens are omitted from CLI status. Back up SQLite with its backup API, not a live bare file copy.
A lost database is not safe to reconstruct as an empty queue while workers may still run: stop/inspect all workers,
restore authority and reconcile GitHub ownership first.

Outbox events post coordinator status on the originating issue, without guessing a recipient or sending email/Slack.
Event markers recover a lost POST response on the next scan. Delivery is at least once; GitHub offers no exactly-once
comment transaction. Use one notifier. API failures leave pending rows and surface service errors. Logs are private,
mode 0600, outside repositories; never upload raw agent/test output automatically. Monitor service stdout/errors and
outbox age locally. No external paging endpoint has been deployed or inferred.

## Supported adapter and deployment

`runner.py` invokes documented `codex exec --sandbox workspace-write --json` with shell network access disabled.
It does not disable sandbox rules, request full access, expose controller credentials or rely on issue comments
starting an agent. A trusted controller clones a read-only mirror, creates `codex/<issue>-worker-a<attempt>`
from the freshly resolved base, and removes its local remote. Controller Git commands ignore system/global config
and hooks. The container mounts only that disposable checkout and its .git read-only; model calls use the private proxy.
It never mounts the Docker socket, controller DB, GitHub token, local server or real accounts.

Tests run in a separate container with `--network none` and no model authentication. Dependencies/SDKs must be
preloaded into the reviewed image. Agent containers use an operator-provisioned network restricted to model
service endpoints; **a named Docker network does not itself enforce that policy**. Configure host firewall/proxy
rules before setting `isolated_host=true`. No server/private LAN routes, DB credentials, SSH keys or host HOME
belong in the worker environment. Use a dedicated Linux worker host/VM, not the live DSP/Claude test machine.
The image must be pinned to an immutable SHA256 digest and contain the reviewed Codex CLI, git, Python/.NET
and necessary restored offline dependencies. No installation or network-dependent restore runs in offline tests.

The CLI uses a documented custom Responses provider (`ffxi_proxy`, `requires_openai_auth=false`),
with no worker-side key/auth file. Deploy a private Responses-compatible proxy on the restricted model
network; it holds the inference key outside every agent/test container, restricts upstream endpoints/models,
and enforces spend limits and worker-network admission. This is not a publicly unauthenticated proxy.
No proxy, model key, firewall or image is provisioned here. The controller never acquires keys, repurposes
connector tokens or copies browser login. Tests have no network and no proxy access.
Official provider configuration: https://learn.chatgpt.com/docs/config-file/config-reference
and https://learn.chatgpt.com/docs/auth .

Deployment procedure (after review/merge by Claude/owner):

1. Provision the isolated Linux host/image/model egress and private inference proxy. Confirm model calls work through the private proxy
   inside the reviewed sandbox without live-server routes; confirm test container network isolation.
2. Keep trusted mirrors updated with the target commits, using a separate fetch process. For the DSP mirror,
   use the `valhalla` remote; never upstream `origin`. The worker never pushes to either remote.
3. Copy `tools/autonomous_worker/config.example.json` to a private config outside git. Set persistent DB/log
   locations, immutable image digest, private proxy URL, network, and repository mirrors. Set
   `FFXI_GITHUB_TOKEN` only in the controller's service environment: scoped contents/issues/PR write on these
   repositories, no administration/secrets permission. Repository policy may still require a human for protected operations.
4. Supply reviewed **offline-only** test argv arrays matching each repository's applicable CI gates. The example
   provides xiheadless's mandatory dotnet gate; DSP and Toolkit intentionally have no default broad test command.
   Add issue-specific Python tests too, e.g. #50 fairness tests. Resolve existing compile/CI baseline failures
   rather than disabling gates. Check ID/SQL/source rules manually before approval; dispatcher does not certify them.
5. Run discovery, inspect returned hash/ownership/base/dependency/conflict results, and authorize only #57 or #50
   with its current hash (do not authorize #57 again while PR #60 owns it). Keep independent dispatchers paused.
6. Run simulations and one external attempt. Review its draft PR, private logs, event/outbox history and termination.
   Only then enable the long-running controller service with restart-on-failure and persistent volume backups.

From repository root:

```sh
python -m unittest discover -s tests -p test_autonomous_worker.py -v
python -m tools.autonomous_worker discover --config /private/controller.json
python -m tools.autonomous_worker status --config /private/controller.json
python -m tools.autonomous_worker run --config /private/controller.json --once
python -m tools.autonomous_worker run --config /private/controller.json
```

`discover` does not enqueue/claim/write GitHub. `run` requires deployment preflight before claims and posts
status through the outbox. The running service scans every 15 seconds. It can run without the hourly ChatGPT
watcher; that task remains a read-only observer. There is no need to change its prompt to pretend it launches jobs.
No new privileged Actions execution workflow is introduced; `autonomous-worker-tests.yml` runs simulations only.
The controller creates branches/commits/PRs through GitHub's Git API targeting the exact allowlisted repo; it never
pushes main, force-updates a ref, deletes a branch, merges or approves its PR. Source/ID/SQL/local acceptance sections
remain explicitly unresolved in generated draft PRs until coordinator review. Required GitHub CI remains independent.

Recovery example (only after actual inspection):

```sh
python -m tools.autonomous_worker resolve --config /private/controller.json \
  --job 'sarthax/xiheadless-dsp#50' --expected-state uncertain \
  --evidence 'Inspected dedicated daemon: no worker remains; no branch or PR was published.'
```

Resolution does not edit GitHub labels, close issues, merge PRs or restart the same issue. Coordinator reconciles
in-progress/needs-local-test labels and existing PRs explicitly. Resolved issues are never silently re-enqueued.

## Actual demonstration and limits

The initial 18 non-destructive simulations passed before the real launch; the completed suite has 24 passing tests. A genuine session subagent implemented xiheadless #57
and opened https://github.com/sarthax/xiheadless-dsp/pull/60 on `codex/57-mcp-developer-guide`, head
`db2b485dd482c5cc1a2a70096fa66a692cf31556`. Only `docs/MCP_DEVELOPER_GUIDE.md` changed. It source-checked
27 relative links and five commands; .NET runtime tests were unavailable and no live tests ran. Root inspected the
PR file list and posted the coordinator handoff on #57. State is awaiting_review, with ownership held by that PR.
#50 remains unclaimed and can be an external-runner acceptance candidate after deployment and fresh validation.

The demonstration used a session-local SQLite record; durable public status is the issue comment/private PR.
It does not prove a persistent host or the external Codex-container adapter is deployed. No Docker/Codex executable
or authenticated external runner was available in this session. Container invocation/publication are tested with
synthetic mocks, not represented as a genuine external run. The hourly task was not changed.

Functioning here: GitHub audit, offline transactional state/ownership/concurrency/retry/outbox simulations,
synthetic editing-to-draft-PR adapter test, and one real ChatGPT session worker with an actual scoped PR.
Requires deployment: persistent service/volume, hardened image/network, private inference proxy, controller GitHub
credential and reviewed per-repo test policy. Not automated here: scheduled ChatGPT-to-subagent launch, external
runner provisioning, live testing, review/merge, and arbitration against workers ignoring central ownership.
