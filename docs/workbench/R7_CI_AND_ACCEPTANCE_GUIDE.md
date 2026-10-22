# R7 GitHub CI and acceptance guide — 2026-10-21

**Scope:** release/operator guide for [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197). Baseline `main@972ff6fa4337cb5d29a3c8c3eb68c73245f24bb9`. No local gameplay, GM, DB-write, packet-send or XIHeadless local-agent work is authorized by this guide.

## What merged in R6

Canonical optional Contract v2 #1285, unified editor #1283, evidence readiness #1287, authoritative non-executable readiness matrix #1292, offline validator #1294, distinct capability backlog #1293, and nine domain scenario documents/JSON drafts: #1277, #1279, #1280, #1281, #1282, #1286, #1289, #1290, #1291.

All **73** staged cases have `execution_status=design_only`, `runner=unassigned`, `verdict=NOT_RUN`. The matrix classifies **5 observe-now**, **2 needs-readback**, **57 needs-mutation**, **9 needs-deploy**. Only `MOG-09` and `INV-OBS-01` are historical entries in the separate v1 executable catalog; a prior narrow MOG-09 runner is not a new gameplay verdict for staged data.

## Offline GitHub verification (merged in PR #1305; main push verified)

The merged pre-R7 workflow fails after automatic deletion of old `spec/*` branches; do not work around it by recreating stale branch names.

- **`integrated-main`:** on a PR, filtered `push` to main or manual workflow dispatch, the corrected workflow checks out complete Git history. It reads **the same checkout tree's** nine staged drafts, single #1292 matrix, manifest and canonical v1 catalog. It checks unique IDs/lanes, source citation syntax, UNKNOWN, disabled permissions and non-promotion, and requires each original pinned PR commit to be a merged ancestor whose staged JSON blob is byte-identical. This is historical Git integrity, not deployed DSP attestation.
- **`staged-pr`:** manual `workflow_dispatch` only, for *future* revised domain source PRs after review of a new head snapshot. Fetches `refs/pull/<number>/head` as **data only**. The observed SHA must match the reviewed matrix; missing/deleted/moved refs fail with explicit errors. No fallback to deleted `spec/*`, main, or untrusted source code.
- **In both modes:** synthetic negative tests, fail-closed `contract_v2`/source URL/sha256/permission/readback validation, source-aware 73-case assertions and untouched canonical catalog checks. The workflow does not contact DSP, an XIHeadless runner, client, GM, SQL, or packet services.

**Observed real post-merge run:** [R6/R7 Domain Readiness Validation #39684273477](https://github.com/sarthax/FFXI-Mission-Toolkit/actions/runs/39684273477) ran on GitHub Actions event `push`, branch `main`, exact #1305 merge SHA `986f781ed1fe61000b2ca62552018061441b7522` and succeeded with 41 synthetic tests: `mode=integrated-main`, `total=73`, `matrix=CONSISTENT_WITH_PINNED_PR_HEADS`, `source_provenance=PINNED_PR_BLOBS_MATCH_INTEGRATED_HISTORY`, `source_authenticity=NOT_ATTESTED`, `deployed_revision=UNKNOWN`. **This is not an independently observed `workflow_dispatch` run or a gameplay verdict.** For future manual validation use **Actions → R6/R7 Domain Readiness Validation (Offline) → Run workflow → branch main → validation_mode integrated-main**. Use `staged-pr` only with still-available PRs and a newly reviewed matrix pinning their exact source HEADs. Never treat deleted old refs or failed staging as a successful integrated-main check.

## Confidence vocabulary and acceptance gaps

| Layer | What offline proof establishes | What remains unverified |
|---|---|---|
| Source specification | Exact syntactically valid repo/path/revision/line citation; original merged PR blob retained | Authentic source file bytes, runtime-loaded DSP revision/config/schema, cross-revision drift, actual Lua/SQL behavior |
| Scenario metadata | 73 unique design records, fixed lanes, no unreviewed oracle/permission promotion | Gameplay execution, independent expected-value oracle approval, actual GM/packet/SQL readbacks |
| Evidence review | Typed noncanonical source/identity uncertainty, UNKNOWN/BLOCKED projection boundaries, intact indexed references | Original physical capture bytes/hash, parser/decoder versions, actual client and server identity agreement |
| Observation readiness | Five *conditional* read-only candidates | Explicit approved test character, bounded access, complete snapshots, independently observed client/server comparisons |
| Chocobo | Nine deployment-blocked designs | Migration applied, server-side implemented features, rollback acceptance, live gameplay |
| CI results | Offline code/test result for exact Git commit | End-to-end GUI operator workflow, observed gameplay PASS, cleanup assurance, reproduction under accepted XIHeadless leases |

Record every local acceptance separately with owner/operator approval, original evidence references, exact client/DSP/Toolkit/XIHeadless hashes, permission scope, snapshot completeness and cleanup result. Unknown observation is **UNKNOWN**; contradictory evidence may be **BLOCKED** pending review; neither means gameplay FAIL.

## R7 handoff and no-overlap rules

1. **Agent C** owns canonical `scenario_contract_v2*.py` and source-to-step schema/compatibility, #1259/#1302. Publish accepted field shapes before consumer changes.
2. **Agent D** owns capture reviewer/readiness projections, #1262/#1198/#1202; no editor or schema rewrite. An exported sidecar is never auto-approved evidence.
3. **Agent B** owns Guided/Advanced Scenario Developer JS/UI and editor model for Phase 2, #1302, consuming C/D reviewed types. No auto-execution or auto-oracle approval.
4. **Agent E** owns bounded read-only fixed-query observability and contracts, #1295–#1300, with explicit unknown/grant/completeness behavior. No local XIHeadless assignment or arbitrary SQL.
5. **Agent A** owns release baseline, GitHub CI, documentation, tracking and merge-queue review. No merge without owner authorization and applicable eligible reviewer; a GitHub COMMENTED review is not APPROVED.

**Open:** #1197 end-to-end supervised import/cleanup, #1198 oracle provenance, #1202 idempotent evidence ingestion, #1259 canonical semantics beyond foundation, #1261/#1262 expanded authoring/evidence acceptance, #1295–#1300 new readback implementations. Narrow domain spec-authoring issues may close only upon explicit proof their *design* acceptance is met; closure says nothing about runtime acceptance.

## References

- [Canonical 73-case matrix](SCENARIO_DOMAIN_READINESS_MATRIX_2026-10-21.json)
- [Distinct R6 capability backlog](R6_DOMAIN_OBSERVATION_CAPABILITY_BACKLOG_1197.md)
- [Active workbench roadmap](ROADMAP_CURRENT.md)
- [Scenario & evidence roadmap](SCENARIO_EVIDENCE_WORKBENCH_ROADMAP.md)
- [Merged R7 post-merge validator #1305](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1305) — [verified `push` workflow run](https://github.com/sarthax/FFXI-Mission-Toolkit/actions/runs/39684273477)
