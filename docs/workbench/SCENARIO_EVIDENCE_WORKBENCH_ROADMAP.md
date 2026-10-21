# Scenario & Evidence Workbench — bidirectional testing roadmap

Status: PROPOSED / planning. Parent: [Toolkit #1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197). Existing related work: #1198 (oracle provenance), #1200 (catalog/preflight), #1201 (run controls), #1202 (import), #1207 (coverage), #1208 (guided authoring), #1249–#1254 (domain expansion), #1255 (spec-driven runner); XiHeadless #42/#47/#49/#105/#107/#122/#123/#126.

## Vision

Create a unified human-readable, evidence-grounded FFXI gameplay testing workbench.

**Forward:** feature/behavior and DSP source -> human-reviewed BDD scenario -> controlled actions -> observed effects -> independent oracles -> verdict/evidence.

**Reverse:** consented/imported capture or run -> preserve raw source -> decode/normalize -> correlate to entities, dialogs, packet fields, source code and state -> reconstruct an *observation* timeline -> propose a **draft**, never automatically a normative oracle -> review/bind/execute.

Use existing Toolkit GM command catalog, items, inventory containers, entities/NPCs, key items, dialogs/CSIDs, Feature/Behavior Trace, capture tools, zones and bounded server readbacks as adapters. Do not duplicate those catalogs. XIHeadless owns bot actions, lifecycle and supervised execution; Toolkit owns feature context, authoring, display, provenance and import. DSP Lua/SQL at pinned commit is the expected-outcome oracle when actually supported by source. A machine may propose relationships but cannot invent IDs/values or promote observations to normative truth.

## Canonical model and contract

Extend existing `data/testing/test_specifications.json` rather than fork it. Preserve import compatibility with legacy v1 evidence and MOG-09.

- Suite/feature/scenario: immutable case ID; stable revision/digest; plain-language purpose, risk/business value, ownership, tags, related requirement and trace refs.
- BDD: `given`, `when`, `then`, ordered readable `steps[]` with stable IDs, action intent, action capability bindings, expected outcomes, independent assertion IDs, readback requirement, optional manual checkpoint, safety and rollback requirements.
- `assertions[]`: existing expression/observed/expected fields retained; source file:line + commit for each concrete ID and expected value, explicit UNKNOWN and blocking gap for absent proof.
- Separate specification maturity (draft/source-backed/reviewed), lane (observe-now/needs-readback/needs-mutation/needs-deploy), execution lifecycle (queued/accepted/running/completed/cancelled/interrupted), and gameplay verdict (PASS/FAIL/BLOCKED/UNKNOWN). Dispatch or completion never imply gameplay PASS.
- Evidence: run ID, scenario+step+assertion version, original immutable artifact pointer/hash, client/server observer, capture/packet decoder version, timestamps, DSP/headless/Toolkit revisions, fixture/account authorization reference (redacted), completeness indicators, confidence/uncertainty and cleanup confirmation. Keep historical recorded and recalculated verdicts side-by-side.
- Readable explanation for every expected/observed outcome; drill down to raw values and packet/source provenance. Never overwrite original evidence or historical spec revisions.
- Capability registry records known MCP verbs, arguments, observation endpoint, decoder availability, permission/mutation class and local acceptance status. Absence is a blocker, not an automatic instruction to create packets.

## UI

1. Scenario Library: feature/domain/suite filter, search, types (positive/negative/boundary/persistence/recovery/observation), readiness, source maturity, historical outcomes and blockers.
2. Scenario Detail: purpose, rationale, Given/When/Then, preconditions, numbered steps, expected vs observed by step, explicit uncovered claims and evidence provenance; technical drilldowns to GM catalog, item/entity/key-item/dialog lookups, packet and source links.
3. Manual Scenario Developer: guided and advanced modes round-trip a single canonical spec; reorder steps, choose catalog-backed parameters, write expectations, bind assertions/readbacks, lint references and validate permissions. Save draft without execution. Require explicit owner approval for mutating cases.
4. Matrix: requirements x scenarios and observation/assertion coverage, distinguishing specified, executable, executed and verified (no inflated pass/coverage percentages).
5. Evidence Timeline & reverse authoring: import raw capture/run, decoded vs inferred event labeling, source/behavior candidates and a *proposed* reviewable scenario. Machine-assisted suggestions stay provisional.

## Delivery slices and owners (parallel-friendly)

**Gate A — contract / schema first (P0):** schema extension, migration/backward compatibility, deterministic validator, sample MOG-09 and INV-OBS-01 including unknown preconditions. Own only `data/testing/test_specifications.json`, dedicated schema/validator/tests; coordinate any shared JSON writes with #1249–#1254. No mutations or live tests.

**Gate B — read-only scenario reader (P0, can prototype against contract draft):** improve existing feature-testing details with narrative/steps/expected/observed/unknown, source drilldowns and legible evidence confidence. Use synthetic fixtures. Avoid modifying writer/runner paths.

**Gate C — catalog-backed manual editor (P0/P1, after contract accepted):** draft CRUD, validation, step reorder, reusable pickers/adapters for GM/items/NPCs/key items/dialog/trace. Fail closed for unsupported or mutable actions. UI agent owns views/routes/editor tests only; adapter agent owns read-only catalog APIs with separate files.

**Gate D — coverage and history (P1, parallel after schema):** extend #1207, preserve comparisons and run provenance via #1202; no synthetic PASS inference.

**Gate E — execution (P1, gated):** #1255 spec-driven observation runner after source-backed observe-now shortlist and accepted XiHeadless #47/#105 contracts. XIHeadless owns process/session control; local operator owns acceptance, DB grants, pooled characters, controlled mutations.

**Gate F — reverse capture-to-scenario (P1 design now, implementation after evidence shape):** normalized timeline provenance adapter using existing capture parsers; deterministic supported packet decoders before optional LLM proposals; drafts only. No automatic acceptance or execution.

**Gate G — intelligent investigation and campaigns (P2):** explain failures, suggest missing tests/packet gaps, safe run comparisons, guided debug and regression coverage. Requires #107/#126 safety and evidence comparability.

## Domain-agent coordination

Before spec-writing agents (#1249–#1254) generate domain PRs, share the new optional narrative/step fields and require purpose, Given/When/Then, steps, expected observed outcomes, source citations per value, UNKNOWN markers and capability/readback gaps. Keep domain PRs isolated; shared readiness/spec JSON changes must reconcile sequentially from current main. No agent may invent client DAT IDs, execute GM commands, run clients, query live DB, or self-merge.

## Acceptance exemplars

- MOG-09 viewer presents readable negative-behavior narrative, step-level 6 assertions, source refs and clear warning that recorded PASS was recalculated from imported evidence, not newly independently authenticated.
- INV-OBS-01 remains design-only until full inventory completeness/persistence boundary is independently observed.
- A manual draft for a known NPC interaction binds a real entity/source citation; missing packet/event oracle displays UNKNOWN, does not save fabricated IDs and cannot auto-execute.
- Reverse evidence from a synthetic event timeline creates a clearly tagged DRAFT with observed steps and missing expected oracle; never yields PASS.
- Offline tests prove round-trip preservation, preexisting v1 importer compatibility, malformed/missing source, unsafe capability blocking, and prior-run stability after scenario revision.

## Release controls

Separate code CI, schema contract tests, dry-run validation and local DSP gameplay acceptance. No merges of domain PRs by their author; no live execution without explicit operator authorization identifying disposable account, character and case. Do not weaken repository AGENTS.md or XiHeadless pool quarantine, cleanup and retry policy.
