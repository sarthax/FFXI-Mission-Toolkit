# Issue #1262 — capture evidence to manual Scenario Developer draft handoff

Status: **synthetic-only, isolated draft PR #1271**, no live-client use.
Indexed normalization [#1265](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1265)
and optional BDD schema [#1263](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1263)
are merged. The accepted schema validates complete specifications; it does **not**
authorize converting capture observations into expectations, assertions, or executable tests.
Parent [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197);
planning [#1258](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1258).

## Concrete integration contract

`workbench.captures.scenario_handoff.reconstruct_review_draft(con, capture_id)`
is a **read-only** adapter. It first calls the source-local, bounded capture
normalization in `src/workbench/captures/scenario_draft.py` from #1265, then
converts the returned rows into numbered reviewer steps, candidate identities,
human-readable observations, independent evidence references, uncertainty and
review decisions. It supplements #1265's existing four source tables with
source-scoped **ordinary-item** records from the existing indexed
`capture_structured_records` table only. That supplementary query never opens
`payload_json` or raw files and uses existing source-row locators.
The original `capture_ki_events` lane stays distinct from ordinary items.

Synthetic fixture entry:
`python test_fixtures/test_evidence_to_scenario_handoff.py`.
The fixture proves an NPC interaction reconstructed from a bounded contiguous
`capture_events` group, EventView message/event ambiguity, ordinary item and key
item candidates, raw packet metadata, source hashes and conflicting NPC labels.

## Type and evidence rules

| Output | Meaning |
| --- | --- |
| `DECODED` | **Existing capture parser** recorded this field; not new packet decryption, independent source verification, or DSP binding. |
| `INFERRED` | Only a proposed relationship, such as source-local adjacent event rows. Not causality or game transaction proof. |
| `AMBIGUOUS` | Conflicting NPC labels, several candidate values, or ambiguous EventView MesNum event/message typing. Retain all alternatives. |
| `UNSUPPORTED` | A raw packet opcode lacks an independently applied decoder; no packet action semantics assigned. |
| Source state `AMBIGUOUS` / `UNVERIFIED_SOURCE` / `UNRESOLVED` | Multiple, unmatched or absent source locators/hashes. Never silently promote one source. |

Every `step.evidence_refs[]` points to an `evidence_map[ref_id]` entry
containing **original** `capture_id`, normalized table, full source-scoped row
key, source filename, SHA-256 as indexed, parser name/version/status when
present, line/byte span and source-local timestamp/clock uncertainty. Ref IDs
are deterministic synthetic *tooling identifiers*, not NPC, packet, item, CSID,
message, or other gameplay IDs.

Source-local event grouping reuses
`src/workbench/runtime/interaction_reconstruction.py:10-93`.
`src/workbench/captures/timeline_alignment.py:1-33` says independent clocks
are not implicitly synchronized. Neither an event group nor an outgoing packet
proves server receipt or expected behavior. The adapter deliberately emits
source **lanes**, not a fabricated merged chronology. It does not associate
packet rows with event rows just because their sequence numbers match.

## Identity and human-review boundary

Only source-recorded candidate identities are suggested: zone, NPC/entity ID
and name, event hexadecimal field, *dialog message ID* (not equated to event
or CSID), EventView `mes_num` (**AMBIGUOUS message/event**), key-item ID,
ordinary item ID and raw packet opcode. These are not automatically resolved
to canonical DSP IDs or Feature Trace nodes. Missing values remain absent.

The proposed reviewer choices on each binding are `ACCEPT`, `EDIT`, or
`REJECT`, initially `PENDING`. The pure
`apply_binding_decisions(draft, decisions)` helper requires an explicit bounded
review note, records an edited proposal *separately* from source value and
never changes source references or approval gates. `review_complete` only
means the candidate labels were considered. It **never** grants permission to
save an executable scenario or establishes an expected gameplay oracle.

## Accepted #1263 canonical schema projection (blocking contract)

`canonical_specification_seed` mirrors proposed optional fields
`purpose`, `rationale`, `behavior.given/when/then`, `steps[].id/title/intent/
expected/assertion_ids/evidence_refs/confidence_note`, and
`authoring.state/execution_policy/evidence_provenance/blocking_gaps/
review_required`. Stable per-step evidence references are carried separately
in `canonical_step_evidence_map` and the immutable source `evidence_map`.

**The seed intentionally does NOT pass the current or proposed
`validate_spec` contract**, because capture cannot supply authoritative
`feature_id`/`case_id`, allowlisted canonical `observations`, source-proven
`assertions`, normative `expected` values, operator authorization, or
required preconditions/cleanup. Those fields are nullable or empty, and
`steps[].expected` explicitly says `UNKNOWN`, with empty assertion and
canonical evidence-reference bindings. Making a syntactically valid executable
or saved scenario by inventing fields would violate #1262 and #1263. A future
human-reviewed mapper must fill these **after** the canonical contract is
accepted. Do not send this seed to `spec_drafts.save_draft`,
`feature_testing.importer`, `draft_preview.preview_draft`, XIHeadless, or
live tools.

Review results never alter `canonical_specification_seed`;
they annotate candidates in the surrounding noncanonical handoff envelope.
The outer `canonical_validation_status` remains
`BLOCKED_REQUIRES_HUMAN_SOURCE_BACKED_AUTHORING`,
`scenario_status=DRAFT_REVIEW_REQUIRED`, `observation_verdict=UNKNOWN`,
`normative_expected=null`, and `execution_enabled=false` even when every
candidate binding is accepted.

## Capability gaps / manual owner checks

1. **Raw source integrity:** the preview preserves indexed hashes, but has not
   rehashed local client files at review time. Corrupted/missing source bytes or
   ambiguous ownership need separate operator validation.
2. **Decoder provenance:** EventView/IDView fields are existing parser results.
   No new packet decoder has been written or run. A live packet interpretation
   would require an attested decoder/revision and byte coverage before use.
3. **Authoritative bindings:** zones, NPCs, item/key-item identities, event/CSID
   and dialog message namespaces need locally available client catalogs and
   pinned DSP source references, exact file:line + commit and hook/branch
   preconditions. No matching by names or numeric coincidence.
4. **Temporal/causal constraints:** ambiguous zone, contradictory labels,
   independent stream clocks and missing/incomplete source tables remain
   blockers. The existing grouping is a review heuristic.
5. **Schema/editor/importer:** #1263 is merged but the seed is still incomplete;
   #1202 must provide a provenance-preserving evidence import handshake;
   #1261 owns UI and save workflow. This prototype does not edit those files.
6. **Bounded output:** max 100 proposed steps; overflow is counted and
   explicitly flagged. Empty capture tables cannot establish absence of
   gameplay behavior.

No real client captures, DAT data, server writes, GM commands, bot controls,
live DB access, or gameplay validation were used. CI is synthetic software
validation only, not independent gameplay acceptance.

## Offline reviewer workflow extension (PR #1271, current slice)

**Entry point (read-only, local indexed database):**

```powershell
python -m workbench.captures.scenario_review_offline --database "C:\\local\\capture-index.sqlite" --capture-id 1 --output "C:\\local\\capture-review.html"
```

This creates one **offline HTML file**, not a Workbench route. Keep the file
private: it contains indexed actor/item/packet metadata and physical source
filename/hash pointers. The source index is opened with SQLite
`mode=ro` and `PRAGMA query_only=ON`; only the expressly requested HTML
artifact is written. No raw capture is copied.

The review page provides source-local timeline sections (not a fabricated
cross-source chronology), explicit confidence/uncertainty, source reference
detail (filename, indexed hash, exact row key, original line/byte span,
parser name/version, packet metadata and clock basis), and candidate
inter-source groups. A fixed allowlist of existing indexed parser fields
(`recorded_metadata`) displays event opcode/direction/option/message,
EventView packet class and MesNum, item/KI identifiers, and raw packet
opcode/injection/block markers. Raw packet bytes and opaque structured
payload JSON are never copied into the review export. A grouping requires the same exact recorded zone label.
Where an explicit NPC/entity field also matches, the relationship still says
**INFERRED**, `UNVERIFIED_CROSS_SOURCE` and `UNPROVEN` causality. Where
only the zone label agrees, it says `MATCHING_ZONE_LABEL_ONLY`. Neither
is a proof of the same entity, causation, transaction completion, or order.

Reviewers make explicit **ACCEPT / EDIT / REJECT** decisions independently
for each proposed step summary and each proposed ID/identity binding. The
original observed summary, source identifier, hash and row provenance are
never mutated; the edited value/title is stored alongside the source.
All decisions require a note, and missing decisions remain PENDING. The
"Export design-only review JSON" control exports an explicit offline
`offline_capture_review_decisions_v1_NONCANONICAL` envelope and the
original immutable projected evidence bundle. Export is a browser download,
not a database write, approval, editor save or execution.

The local replayer
`scenario_review_workflow.replay_offline_review(original_draft, json_payload)`
verifies the base projection checksum *and equality of the original
observation bundle* before applying any submitted decisions through
`apply_binding_decisions` and `apply_step_decisions`. The checksum detects
changes to the **indexed projection**; it does not attest original physical
source bytes or independent client/gameplay observations. A tampered
verdict, source reference, runner, expected oracle or extra field fails
closed. Fully reviewed candidates remain **manual authoring required**,
`UNKNOWN`, `normative_expected=null`, and `execution_enabled=false`.

**Provisional Given/When/Then:** `behavior_preview` proposes only a
description of what was recorded/reviewed. `THEN` remains normative
`UNKNOWN`. The accepted canonical shape is mirrored in
`canonical_specification_seed`, but required feature/case IDs, independent
observations and assertions must still be authored and verified. No attempt
is made to force an invalid source into a valid schema using fabricated
IDs or oracles.

**Continue in Scenario Developer contract:**
`manual_editor_handoff(...).continue_in_scenario_developer` advertises
`destination="Scenario Developer (#1261)"`, `route="/scenario-developer"`,
`status="MANUAL_HANDOFF_ONLY"`, `automatic_import=false`,
`payload_kind="UNTRUSTED_OBSERVED_GUIDANCE"` and `no_execution=true`.
A user must open Agent B's separate editor manually, create a new design-only
case and provide independently sourced expectations, case identity, bounded
observation/assertion bindings, preconditions and cleanup. This JSON is
**not an existing POST payload** for Agent B's validator, draft saver,
evidence importer or headless runner. There is deliberately no cross-surface
session transfer, injected query parameter or auto-save.

**Acceptance tests:** `python test_fixtures/test_capture_reviewer_workflow.py`
runs synthetic, read-only reconstruction, timeline grouping, contradictory
source identities, orphan/ambiguous evidence, manual review roundtrip,
original evidence immutability, unsafe bundle tampering, HTML escaping and
offline CLI DB byte preservation. Registered in Workbench Regression.
Actual browser click-through and real capture semantics remain **local
operator acceptance**, not CI claims.
