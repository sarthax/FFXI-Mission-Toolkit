# Current Workbench Roadmap

**Updated 2026-10-27 — owner-directed work.** The A–E multi-agent coordinator experiment is retired. [#1348](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1348) and its policy [#1398](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1398) are closed. Historic issue assignments, reviewer waves and old SHA/CI snapshots are **not** current instructions.

Older release history and technical evidence remain in [the archived roadmap](archive/ROADMAP_CURRENT_PRE_COORDINATOR_RETIREMENT_20261027.md) and in [ROADMAP.md](ROADMAP.md). These sources retain useful implementation history but should not be treated as a current backlog.

## Immediate product outcomes

| Priority | Deliverable | Current truth / acceptance gate |
| --- | --- | --- |
| P0 | **Usable Scenario Suite v2 Results screen** | [#1406](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1406) is **NOT ACCEPTED** end-to-end. The user wants summary first, all steps equally visible, readable FFXI actions/expected/observed values, and expandable raw IDs/logs. Offline models/DTOs [#1422](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1422), [#1426](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1426) and acceptance [#1428](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1428) are not a shipped UI. Implement and validate actual operator workflow; respect outstanding safety/privacy issues. |
| P0 | **Authentic MOG-09 evidence integrity** | Local source handoff [#1420](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1420) contains useful runner-origin evidence but still needs reconciliation of report count, original-vs-sanitized hash lineage, and screenshot/run-ID privacy. Runner-reported PASS is not an independently authenticated oracle PASS. |
| P0 | **Supervisor security tests** | Actual matched-route authentication-before-validation and zero-read tests [#1333](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1333) remain a blocker to [#1324](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1324). No bypass or silent approval. |
| P1 | **Human scenario authoring and versioned catalog** | Preserve [#1406](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1406) acceptance: author → review → publish → run → understandable results. Typed/game-semantic prototypes are proposal-only, not executable/approved registries. Prioritize one end-to-end usable slice over proliferation of synthetic contract PRs. |
| Ongoing | **Other Toolkit modules and bugs** | Owner/local agent selects concrete, user-visible bugs and features directly from current GitHub state and testing. Do not infer priority from old coordinator waves. |

## Working rules

- **One owner-directed task at a time or a small coherent batch:** branch/PR, tests, concise evidence handoff, acceptance and merge decision. An A–E agent assignment or rotating independent reviewer is **not** required.
- Evaluate unfinished draft PRs on their merits: retain meaningful code/tests, remediate or close superseded proposals with an explanatory note. **Do not mass-merge, mass-close product bugs, or convert test-only success into gameplay acceptance.**
- Current `main`, actual PR statuses, CI at exact heads, live browser/gameplay evidence, and owner decisions override dated snapshots.
- Local/live server work is performed only by the owner/authorized operator. Protect credentials, player identity, captures and source integrity.
- Update this page when an actual release, meaningful product slice, or verified blocker changes; do not append per-agent status waves.

## Archive and closeout

The old multi-agent coordinator's run logs and issue threads remain visible for audit. The hourly ChatGPT coordinator automations for Toolkit and XIHeadless were disabled on 2026-10-27. The owner/local agent may reconcile duplicate or speculative issues separately. This cleanup does **not** assert any unfinished feature is complete.
