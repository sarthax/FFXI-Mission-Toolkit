# AGENTS.md — rules for AI workers (Codex, ChatGPT agents)

FFXI Mission Toolkit / Workbench is an evidence-driven research and admin toolkit (Python >=3.11, package under `src/workbench`).
Workers build and test tool code in parallel; **Claude Code or the owner runs it against the real client data, captures and
server** (none of which are in this repo). This repo is also the **source of truth for how ids, dialogs and entities are
pulled**: the pulls themselves (`dialog.yml`, `entities.yml`, event dumps) are generated locally from the client DATs and are
not stored here, so you cannot read real client ids. Do not guess them.

## Development modes

### Unattended autonomous workers

The issue-claim rules below apply to unattended dispatcher, Codex, or other autonomous workers. They must use a `ready` issue with exclusive file ownership, an isolated PR, and owner/Claude review before merge.

### Interactive, owner-directed sessions

When the repository owner directly instructs an AI assistant in an interactive session, the assistant may work on the requested task without requiring a separate `ready` issue for each slice. Group related work into meaningful branches and PRs, inspect current `main` and concurrent branches before editing, preserve newer work, and run applicable CI/tests. The owner may authorize review and merge of green PRs when repository and tool permissions permit. Never circumvent enforced access controls, merge protections, or a blocked permission decision. Do not force-push or overwrite concurrent work. Local gameplay acceptance remains with the owner or an authorized local operator; CI is not runtime acceptance.

## Unattended worker workflow
1. Take ONE issue labeled `ready`; touch only its "Files owned".
2. Branch from `main` as `codex/<issue>-<name>`; open a PR into `main` using the template; label it `needs-local-test`.
3. Never merge your own PR, never push to `main`, never force-push shared branches.
4. Add or extend tests under `tests/` for what you change and run them (`pytest`). The workflows in `.github/workflows/`
   show which regression suites run on which paths; match them for the area you touch.
5. If a spec is ambiguous or needs local data you cannot see, stop and ask on the issue.

## Hard rules
- **Preserve evidence, separate inference, never manufacture certainty.** This is the project's founding rule (README). When
  evidence is missing, report it as unresolved; do not fill gaps with plausible values.
- **Never invent an id** (CSID, event, message/dialog, mob/NPC, key item, item, packet, zone). Use only values present in
  committed fixtures, existing code, or sources cited in the PR; otherwise `TODO(needs Claude lookup)`.
- **Keep fixtures honest.** New files under `test_fixtures/` must be real excerpts or clearly labelled synthetic data. Do not
  hand-edit captured evidence.
- **Public repo.** Never commit secrets, server/DB credentials, account names, personal paths, `.env`, live client persistent
  credentials, or large raw captures. Do not add client DAT / retail data dumps.
- **Server-affecting actions are guarded.** Do not weaken or bypass the guards on GM / admin / SQL-write / live-client control
  features, and never make a feature write to a live DB by default.
- Respect the `src/` layout and the existing `definitions.d/*.json` domain pattern; follow the surrounding style.

## You cannot do
Read the client DATs, captures beyond `test_fixtures/`, the live server, or run the Ashita live-client bridge. Put every
unverified claim in the PR's **Could not verify here** with exact steps and the expected result.

## Where to look
`README.md`, `docs/workbench/ROADMAP_CURRENT.md`, `docs/workbench/` (design + status docs), `tests/`, `test_fixtures/`.
