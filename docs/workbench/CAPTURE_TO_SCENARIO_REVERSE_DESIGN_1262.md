# Reverse capture → scenario: source-backed capability map and synthetic prototype

Status: **Issue #1262 isolated review draft**, 2026-10-20. Planning prerequisite:
[#1258](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1258)
(Gate F, after importer/schema evidence shape). Not a canonical scenario contract.

## Ground rule

An observed packet, NPC dialog, CSID, event, item/key-item change, or bot result is
**what the capture reported**, never an independent DSP rule or an expected
outcome. An observation-only reconstruction must say **DRAFT_REVIEW_REQUIRED**,
**UNKNOWN** verdict and **no execution permission**. A time-series or
correlated identifier cannot establish that a transaction succeeded.

## Existing components and ownership (main at 7b1825ca)

| Stage | Existing implementation, file:line | Reuse / limitation |
| --- | --- | --- |
| Capture schema | `src/workbench/captures/ingestion/_build_index_impl.py:93-222` | `capture_events` (zone+seq but no clock), `capture_eventview` (zone+seq and optional native `ts`), `capture_ki_events`, `capture_raw_packets`, structured records; distinct per-source identities. Do not globally sort sequence numbers. |
| Parsers | `src/workbench/captures/ingestion/_build_index_impl.py:2052-2058,2276-2281,2369-2380,2655-2662,2725-2730` | Existing CapLog, EventView, whole-session unknown-zone, IDView parsers. Keep undecidable zone/time as unknown. Never introduce speculative packet decryption. |
| Raw packet index | `src/workbench/captures/_raw_packet_ingest_impl.py:108-183,187-190,322-375` | Source-native identifiers and raw hex are retained in the existing index; locator spans and source SHA are attached. The preview exposes metadata and immutable pointers only, not raw packet bytes. |
| Raw-source lineage | `src/workbench/captures/integrity.py:58-155,478-575,579-631` and `src/workbench/core/contracts/capture_row_locators.py:1-56` | Source manifest: hash, parser/version/status; row locators: original filename, hash, line/byte span and basis. Multiple locators are **ambiguous**, not resolved by picking one. An indexed SHA is *not* independent verification that source bytes remain available or unmodified. |
| Clock alignment | `src/workbench/captures/timeline_alignment.py:1-33,72-113` | Distinct epoch/logger/raw/EventView clocks require explicit anchors; without them, source-native timestamps are not a common chronology. |
| Interaction candidates | `src/workbench/runtime/interaction_reconstruction.py:1-16,34-93` | Existing Capture Timeline groups contiguous same-zone/compatible-entity/CSID rows; its `complete_signal` is only a pattern heuristic. No game transaction, success, or server confirmation is inferred. |
| Packet interpretation | `src/workbench/packets/_decode_impl.py:1-24,93-123` | Packetlyzer-dependent real schema/decoder is separate; present adapter never loads it and never interprets opcode meanings. A decoder definition/revision and per-field coverage remain required for future decoded evidence. |
| Capture → graph/source | `src/workbench/captures/correlation/backtrace.py:50-124`, `src/workbench/captures/_related_evidence_impl.py:9-112,214-268` | Existing backtrace finds candidates against graph/packet/entity records. Same-zone numeric entity association is bounded; mes_num/message IDs are explicitly `MESSAGE_OR_EVENT_ID` UNKNOWN until independently typed. No name-only or cross-namespace ID equating. |
| Feature/Behavior Trace | `src/workbench/devtools/features/trace.py:101-128`, `src/workbench/devtools/behavior/scripted_behavior.py:21-67`, `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md:6-11,69-75,127-137` | Feature Trace is cross-source navigation; Behavior Inspector is static Lua/source behavior. Keep their source-backed graph claims distinct from runtime observation and proposed links. |
| Dialog/CSID | `src/workbench/devtools/entities/_profile_impl.py` (capture `event_hex` and `message_id` evidence), `gui/templates/event_view.html`, `gui/templates/dialog.html` | Reuse source-indexed zone/entity context at review time. Do not treat a numeric message ID as globally unique CSID or quote client text not present in the indexed source. |
| Feature-testing results | `src/workbench/server_admin/feature_testing/importer.py:17-55,58-88`, `normalized_evidence.py:1-6,24-73` | Import accepts only allowlisted known feature/case results with revisions, and requires assertion/observation payload for PASS; its MOG-09 normalization explicitly disclaims independent confirmation. **Do not feed a reverse draft into this importer.** |
| Scenario specification | `src/workbench/server_admin/feature_testing/test_specifications.py:17-50`; draft schema on #1263 | Canonical schema owned by Agent A; this lane is a separate noncanonical preview. Do not create spec IDs, expectations, assertions, or persisted revisions here. |

## Read-only prototype contract

`workbench.captures.scenario_draft.reconstruct_observed_draft(con, capture_id, max_rows_per_table=200)`
consumes an **already indexed** SQLite capture, with fixed allowlisted SELECTs
against four source tables. It does not ingest/decode files, persist artifacts,
write DB rows, access a live client, invoke a bot, or create scenario specs.
The test fixture is generated synthetically in memory and supports SQLite
`PRAGMA query_only=ON`.

It emits separate **streams** partitioned by source table and (where available)
zone, with source-local sequencing, unchanged observed identifier fields,
source native timestamps clearly marked *unverified*, raw-file SHA + row locator
references (when present), indexed-only observation confidence and explicit
truncation/missing-source gaps. Existing interaction grouping is surfaced as
**POSSIBLE_INTERACTION_NOT_PROVEN_TRANSACTION**; it does not assert transaction
completion. Packet rows expose only metadata, including injection/block flags.

The preview never emits a normative expected value, independently verified PASS,
action intent, action capability, rollback plan, executable instruction, or
DSP oracle. The placeholder DSP correlation is `NOT_EVALUATED`, not negative
evidence. The record is a **candidate for human authoring**, not an importable
`data/testing/test_specifications.json` record.

## Manual review and downstream integration gates

1. **Source integrity:** verify local raw artifacts against indexed SHA, retain
   source identity and exact spans, distinguish source missing/overlap/parse
   error, and pin parser and packet-decoder revisions. Currently this preview
   cannot attest availability of original raw files.
2. **Causal/time gaps:** review stream boundaries, explicit clock anchors,
   dupes, unknown zones and incomplete table coverage before proposing a
   unified sequence. Raw/decoded/heuristic events must remain separate.
3. **Identity binding:** bind zone-scoped entity, event/CSID, dialog, KI and
   opcode against authoritative client/server catalog evidence; ambiguity is a
   blocker. Packet injection or outgoing dispatch does not prove DSP receipt.
4. **DSP correlation:** use pinned DSP commit + exact Lua/SQL file:line plus
   appropriate hook/precondition/branch context; classify as a **candidate
   source explanation** until independently reviewed. Do not infer an oracle
   from temporal adjacency, message coincidence, or Feature Trace similarity.
5. **Spec promotion:** wait for #1259/#1263 schema and #1202 evidence import
   contract; manual authoring #1261 must explicitly approve the normative
   GIVEN/WHEN/THEN, expectations and independent readbacks. No automatic
   change to viewer #1260, schema #1263, XiHeadless, GM or server state.
6. **Coverage:** no claim that missing tables, source bytes, packet definitions,
   client DATs or DSP source evidence imply feature absence. MOG-09 historical
   evidence remains a distinct imported runner report, not a reverse-created
   fresh verification.

## Validation / could not verify here

Synthetic test: `python test_fixtures/test_capture_reverse_scenario_draft.py`.
The Workbench Regression workflow runs this file on the PR. It exercises
read-only DB operation, separation of event streams, provenance status,
multiple source ownership, cap/truncation, missing table, injected/blocked
metadata and no PASS/oracle/execution promotion.

Not verified here: original source-byte availability, actual EventView/IDView
ingest against a live capture, packet decode accuracy, source identity
correlation to a *pinned* DSP checkout, schema compatibility with the evolving
#1263 contract, or runtime gameplay. These require operator-owned fixture,
local source indexes and separate acceptance; they are **not** prerequisites
to review this offline-only prototype, but **are** prerequisites to promotion.
