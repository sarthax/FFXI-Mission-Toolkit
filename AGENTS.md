# AGENTS.md — contributor guidance

FFXI Mission Toolkit / Workbench is an evidence-driven Python 3.11+ research and administration application under `src/workbench`. Real client DATs, captures and server access are local and must never be inferred from repository fixtures.

## Working model (2026-10-27)
The experimental A–E coordinator, issue #1348, policy #1398, agent-letter dispatch waves and mandatory claim/READY_FOR_REVIEW handoff process are **retired**. Their issues and historical comments remain as evidence, not active assignments.

- The owner/local developer or an explicitly delegated Codex session selects scoped implementation or maintenance work based on current GitHub issues/PRs and actual project priorities.
- Check whether the local developer already owns or completed the work before editing. Use a focused isolated branch/PR and avoid creating unnecessary planning-only issues.
- Use **local-first CI**: run focused offline `pytest`/Node checks during draft development, and keep draft-PR GitHub-hosted test jobs skipped. Before merge, validate the exact final commit SHA with the applicable complete ready-for-review workflows or a documented local full suite; skipped, blocked or previous-SHA checks are not PASS. See `docs/workbench/CI_LOCAL_FIRST.md`. Existing protections and appropriate independent review still apply; no automatic merge or forced push.
- GitHub PR/issue states, code and current test evidence take precedence over archived wave tables. Do not treat old coordinator comments as a dispatch.
- Document reusable design and roadmap changes in `docs/workbench/`, keeping `ROADMAP_CURRENT.md` concise and factual.

## Safety and evidence
- Preserve provenance; distinguish source observations, inference, proposals and validation. Never invent DAT, CSID, mob, event, packet or item IDs.
- Keep fixtures clearly synthetic or accurately extracted. Do not publish client DATs, raw captures, credentials, private account names, personal paths or live server data.
- Do not bypass GM/admin/SQL-write/live-client guards or change live DB state by default.
- Local browser, server, Ashita and actual gameplay acceptance must be performed by an authorized operator. Report **NOT_RUN** where evidence is absent.

## References
`README.md`, `docs/workbench/ROADMAP_CURRENT.md`, `docs/workbench/AUDIT_STATUS.md`, tests and active GitHub issues/PRs. Historical coordinator/agent assignments are not actionable instructions.
