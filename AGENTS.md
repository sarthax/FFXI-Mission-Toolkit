# AGENTS.md — owner-directed development guidance

FFXI Mission Toolkit / Workbench is an evidence-driven research and admin toolkit (Python >=3.11; code in `src/workbench`). **The former A–E multi-agent coordinator experiment ended 2026-10-27.** [Coordinator #1348](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1348) and [policy #1398](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1398) are archived history, **not dispatch or review instructions**. Do not create coordinator waves, claim assignments from old tables, require agent-letter ownership, or generate process-only issues/reviews.

## Normal workflow
1. Follow the owner's current request and current GitHub issues/PRs; check latest `main` and concurrent work before editing. Pick a concrete user-facing problem or verified bug, not a new coordination artifact.
2. Group related changes in a focused branch/PR; describe code changes, tests, and remaining acceptance. Avoid duplicate implementation and overlapping files. A separate `ready` issue or A–E claim is **not required** for owner-directed work.
3. Run relevant `pytest` and CI checks. Never mistake offline CI for live/client/server acceptance; report unresolved verification with reproducible local steps.
4. Follow branch protection and owner decisions. No forced pushes or overwriting another contributor's work; only merge when the owner and repository permissions allow it. Do not demand a prescribed A–E reviewer sequence; use review when appropriate to the risk and repository rules.
5. Keep `docs/workbench/ROADMAP_CURRENT.md` concise and outcome-oriented. Existing historical roadmaps and coordinator threads are archival; don't revive their assignment tables.

## Non-negotiable evidence and safety rules
- Preserve evidence and separate facts from inference. Never invent CSIDs, NPC/item/key-item/packet/zone IDs or pretend source-only or synthetic observations are validated gameplay. Local client DAT/generated mappings and captures are not present in GitHub; require source-backed IDs or explicitly unresolved fields.
- Label fixtures as authentic excerpts or **synthetic**. Never hand-edit captured source evidence to create fabricated authenticity.
- Do not commit credentials, personal paths, account information, live DB dumps, client DAT/retail files or private raw captures. Check privacy before publishing screenshots or run receipts.
- Never weaken GM/admin/SQL-write/live client controls, or write to a live database by default.
- Follow existing `src/` structure, `definitions.d/*.json` and adjacent coding practices.
- The owner or authorized local operator performs real client/server/gameplay tests. Remote code review or GitHub tests cannot claim those checks ran.

## Starting points
`README.md`, `docs/workbench/ROADMAP_CURRENT.md`, `docs/workbench/`, `tests/`, `test_fixtures/`. Prior multi-agent issues/PRs may contain useful technical work; evaluate their code and evidence individually rather than treating their coordinator statuses as authority.
