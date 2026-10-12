# Feature Trace relevance and usability audit — baseline (2026-10-11)

Status: **audit protocol established; real-package execution pending**. This document is not a claim that an actual DSP/LSB package has been executed or scored.

## Verified existing code boundaries

- `src/workbench/devtools/features/trace_benchmarks.py`: benchmark scenarios, including `absolute-virtue`, WotG Cait Sith, NPC, and NM; `evaluate_trace` tests mode, root kind, minimum relationship count, relationship *terms*, and generator availability. It does **not** establish correct identity, relevance, directed path, source locator validity, or completeness.
- `src/workbench/reference/absolute_virtue_demo.py`: explicitly seeded **reference** obtainability graph. It is not a live-server implementation trace.
- `test_fixtures/test_feature_trace_catalog.py`: synthetic provider identity/closure checks, including spawn → group → pool and ambiguous ID handling. This is necessary correctness coverage but not a user-facing relevance evaluation.
- `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`: records provider relationships and conservative evidence/identity boundaries.

## Investigation questions and acceptance cases

| Case | Primary question | Must be easy to find | Must not dominate initial view |
| --- | --- | --- | --- |
| AV implementation | Where is Absolute Virtue implemented and what controls its behavior? | Unique entity identity, spawn/group/pool, relevant Lua entry points and behavior, exact file/row/line evidence; explicit gaps | Virtue obtainability, loosely matched wiki references, unrelated entities |
| WotG Cait Sith | What starts, gates, advances, and completes this mission? | Script and handler, event/CSID, state guards/writes, required NPC interactions, branching, next-state evidence | All NPCs in zone, incidental shared helper usages |
| Ordinary NPC | What happens when I interact with this NPC? | One resolved NPC, script, trigger/guard/effect and source locator | Global zone graph, all nearby entities |

Use a real indexed server checkout plus capture/client/wiki packages *only where relevant*. Record source family, revision/build, indexed table counts and root resolution; never copy private capture contents into audit reports. If no real package is available, report **NOT RUN** rather than scoring synthetic fixtures as real evidence.

## Manual scoring sheet for each case

1. **Root resolution:** exact unique identity, ambiguous, or unresolved; note mistaken aliases/IDs.
2. **Required paths:** enumerate a small set of independently verified source-backed edges, with direction and evidence locator. Score each as present, missing, wrong, or unsupported.
3. **Noise:** count initially displayed edges that are peripheral or irrelevant to the question. Note total edges, relevant edges, and the top five distractions.
4. **Evidence quality:** for each displayed primary edge, record file/line, SQL row/key, capture locator, or **no verifiable locator**. Never promote wiki/reference-only material to implementation proof.
5. **Navigability:** clicks from result → meaningful node → exact source, number of actions, and whether backtracking preserves context.
6. **Branch correctness:** one-hop neighbors, joins, cycles, unknowns, truncation, and alternate path behavior.
7. **Answerability:** can a user answer the primary question without reading an undifferentiated result list? Record yes/partial/no and a short explanation.

Report: precision = relevant initial edges / all initial edges; required-path recall = verified required paths shown / all independently verified required paths; locator coverage = primary edges with valid evidence locator / all primary edges. Mark denominators zero as **N/A**. These are observational measures, not semantic confidence scores.

## Audit execution sequence

1. Export current focused-mode trace results for AV, Cait Sith and one ordinary NPC with the same 1-hop starting budget; preserve raw JSON and metadata outside git.
2. Independently inspect corresponding indexed SQL and Lua evidence to establish a small expected-path ledger, including known unknowns.
3. Score the raw results with the rubric above and take screenshots of the current UI. Compare guided Behavior/Clarified Flow presentation where the same script is available.
4. Identify defects as **root resolution**, **missing provider link**, **irrelevant edge selection**, **evidence explanation**, or **navigation/UI**. Do not fix all categories in one PR.
5. First code slice after measured baseline: **read-only relevance projection** that selects a small primary subgraph based on question/mode, keeps the original result accessible as secondary evidence, and labels exclusions and truncation. No synthetic joins or silent deletion.
6. Retest the three cases; only then build the graph/inspector visual redesign and persistent investigations.

## Acceptance gate for first implementation PR

AV Implementation must present a unique root and a short, source-backed implementation chain, with each edge's direction, reason, and locator. Any missing script or ambiguous identity is explicitly reported. Related but nonessential obtainability and wiki links remain discoverable outside the initial view. The ordinary NPC view must be substantially smaller than its raw all-evidence result. WotG must preserve branching and state guards. Synthetic regression tests are supplementary; a real indexed package run and operator review are required before declaring usability fixed.

## Separation from parallel work

Audit-only changes belong to `audit/feature-trace-relevance-baseline-20261011`. Do not change Live Client, Wiki V2, Character Editor, Behavior Trace, or shared GUI templates during baseline collection.
