# R7: Evidence Readiness → Scenario Authoring provenance (read-only)

**Scope:** Agent D #1262; Feature testing #1198, evidence importer #1202,
R7 editor #1302, epic #1197. This is an additive implementation of the
**merged** R6 Evidence Reviewer (#1276/#1287), not a new decoder, import
contract, canonical `contract_v2` source, or executable scenario engine.

## Contract / consumer boundary

`summarize_capture_readiness(draft)` supplies
`scenario_developer_handoff.read_only_projection`, contract
`capture_readiness_authoring_projection_v1_NONCANONICAL`. The existing
offline Evidence Reviewer displays it only as part of a separate optional
`capture_reviewer_readiness_sidecar_v0_NONCANONICAL`. The unrelated
`offline_capture_review_decisions_v1_NONCANONICAL` envelope, original
`original_evidence_handoff`, and human `review_decisions` remain intact.
**Never POST the sidecar into the existing Scenario Developer review importer**,
copy fields into a saved scenario, or emit an approved assertion. Agent B owns
any later opt-in display and stale-file/inspection protections (#1302).

Additive R7 step field `indexed_evidence_provenance[]` pairs one original
`evidence_ref` with:

| Field | Meaning / trust limit |
| --- | --- |
| `capture_id`, `source_table`, `original_row_key`, `record_class` | Exact indexed capture-row identity, not an independently verified live event |
| `native_timestamp`, `time_basis` | Source-local timestamp; other clocks are **not aligned** |
| `source_locator_status`, `source_file_claims[]` | One or more indexed source-file/line/offset references, not a proof that source bytes still exist |
| `source_filename`, `source_span`, `locator_basis` | Indexed filename, line/offset range and locator type, without raw packets or opaque payloads |
| `locator_sha256_claim`, `manifest_sha256_claim` | Two distinct *indexed digest claims*; matching strings **do not independently rehash either file** |
| `parser_name_claim`, `parser_version_claim`, `ingest_status_claim` | Recorded parser and capture-ingest metadata; recognized status remains **not independently validated** |
| `parser_support` | `INDEXED_RECOGNIZED_NOT_INDEPENDENTLY_VALIDATED` or `UNRECOGNIZED_OR_UNSUPPORTED` |
| `decoder_version`, `decoder_version_status` | `null` / `NOT_INDEPENDENTLY_ATTESTED`; ingest parser version is **not** a packet decoder version |
| `provenance_issues[]` | UNKNOWN/BLOCKED source-ref scoped parser/digest/revision diagnostics |
| `independent_source_authentication`, `indexed_digests_rehashed` | Both always `false` |

The existing fields remain authoritative **within this noncanonical
projection**: `identity_confidence` (EXACT = source record candidate only;
AMBIGUOUS = no chosen ID), `original_evidence_refs`,
`review_decision_original`, `missing_readbacks`,
`expected_candidate`, `oracle_approval_state=UNAPPROVED`,
`readiness_state=UNKNOWN|BLOCKED`, `normative_expected=null`,
`verdict=UNKNOWN`, and `execution_enabled=false`. All suggested
capabilities are *unregistered* and permission=false. A complete, trusted
canonical `contract_v2` is available on main after #1285 merged, but
**this reviewed capture advisory is not a valid canonical spec**: the
historical `contract_v2_adoption` literal remains blocked for compatibility
with R6 consumers until a separately reviewed adapter contract is accepted.
Do not infer it means the canonical schema is still unmerged.

Additional **conditional** proposed readbacks:
`job_state` on event/eventview lanes (server main/subjob, level and ability
prerequisites) and `mob_state` on captured interactions (claim, HP,
despawn). Other existing client/server inventory, furnishings, key items,
quest variables, NPC/event/instance state, temporary items and independent
server receipt gaps remain. The presence of a gap does **not** prove the
scenario depends on that readback; `importance=CONDITIONAL` means an
operator must first establish relevance. All remain unobserved here.

If an indexed source manifest has a missing parser name/version/digest or
an ingest status other than `RECOGNIZED`, diagnose **UNKNOWN** and show the
recorded incompatible/unrecognized metadata. An explicitly conflicting
well-formed locator/manifest hash, pinned source or projection revision is
**BLOCKED**. Neither status is a gameplay PASS/FAIL: gameplay verdict is
still **UNKNOWN**. Repeated capture differences also require comparable
preconditions, instance, source revision and independent server observations.

The existing offline reviewer recomputes the noncanonical typed projection
against the original indexed evidence map and rejects modified source refs,
claimed decoder verification, copied/rehashed digest claims, raised oracle
approval, forged verified identities and execution permissions. A
self-consistent exported file is **not** a cryptographic signature; when
consuming independently, Agent B must compare capture ID, original source
rows and separately scoped
`indexed_observation_projection_sha256` versus
`original_handoff_projection_sha256`, preserving the original review
decisions, without assuming those two digests hash identical data.

## Synthetic acceptance

Dedicated `Capture Evidence Readiness (Offline)` GitHub Actions suite
also exercises: ambiguous NPC candidates, exact source-record-not-client
identity, copied/independently cited unapproved expected-value candidates,
partial client-only inventory with absent authoritative server state, missing
furnishings/key-item/quest/job/mob/instance readbacks, absent parser
name/version/manifest digest, unrecognized parser ingest, changed revisions,
conflicting/unaligned captures, altered source refs, false decoder/source
authentication and forced approval or execution. The Workbench and Src Layout
regressions must pass on **the same exact PR head** before review.

## Future owner-authorized local evidence authentication (not done here)

1. Preserve an operator-selected original physical capture byte stream and
   record immutable capture identity. Independently compute its SHA-256 and
   compare to both indexed source locator and source manifest; capture
   projection hashes are **not** substitutes for this file rehash.
2. Verify parser name/version, input format, decoder schema/version and actual
   supported field semantics against the local installed capture/parser tooling.
   Unknown, unsupported or changed version remains UNKNOWN pending review;
   do not guess.
3. Verify the deployed DSP commit and exact implementation files/line spans by
   independent checked-out bytes and SHA-256. Reconcile source-row NPC/mob/zone/
   CSID/key-item namespaces against independently inspected client DAT and
   server tables, keeping ambiguity explicit.
4. Obtain **authorized read-only** client *and* server evidence for the
   relevant state before/after each operation (inventory, furnishings,
   jobs, KI, quests, NPC/mob/event/instance state, temporary items); compare
   under recorded preconditions and branch guards.
5. A separate human owner must review source-backed normative oracles,
   permissions, capability safety, local provenance and approved execution
   boundaries before any canonical scenario or feature-testing result can
   claim verified PASS. Integrate with #1198 oracle maturity and #1202 import
   reconciliation only through their owner-approved contracts. No live or
   mutating operation is part of this PR.

**Could not verify here:** physical source bytes, local client DATs, local
installed parser/decoder binary and semantics, any server-state readback,
deployed DSP revision, authenticated gameplay or browser/manual UI behavior.
Offline CI confirms producer invariants on synthetic examples only.


## R7 final producer interface reconciliation — Agents B / C (2026-10-21)

This is the **producer contract on draft PR #1308**. The noncanonical
`capture_readiness_authoring_projection_v1_NONCANONICAL` envelope is not
the canonical `contract_v2` namespace and may not be passed to the
Scenario Developer save/validation importer.

- `steps[].step_id` is **the indexed capture observation step ID**, not a
  canonical v1 scenario step. New
  `steps[].canonical_step_id = null` and
  `steps[].canonical_source_association = {
  state:"UNASSIGNED_REQUIRES_INDEPENDENT_CANONICAL_CROSSWALK",
  scope:null, source_refs:[]}` explicitly prohibit inferred step citations.
- Agent C's **draft #1309** proposes an optional canonical
  `contract_v2.source_associations[]` of precisely
  `{scope:"case"|"step",target_id:null|canonical_step_id,source_refs:[...]}`.
  A reviewed case citation does not automatically apply to each step.
  Identity-candidate `parameters[].source_refs` and oracle
  `oracles[].source_refs` are independently scoped. This capture projection
  emits **none** of those canonical records and cannot assert their
  authenticity, revision, digests, approved oracle or permission. Its
  existing metadata preview still leaves `sources=[]`, `oracles=[]`
  and **omits** `source_associations`.
- The source-row `capture_file_locator_state` is
  `INDEXED_FILENAME_CLAIM_NOT_AUTHENTICATED` when an indexed filename
  exists and `NO_INDEXED_CAPTURE_FILE_LOCATOR` when none is recorded.
  **Neither state asserts the physical file exists or does not exist**.
  A missing indexed filename remains UNKNOWN; a source digest conflict is
  BLOCKED only if two well-formed independently recorded *indexed claims*
  actually conflict.
- `parser_support=MISSING_PARSER_IDENTITY_OR_VERSION` on incomplete
  declarations, `UNRECOGNIZED_OR_UNSUPPORTED` on other non-recognized
  declarations, and
  `INDEXED_RECOGNIZED_NOT_INDEPENDENTLY_VALIDATED` otherwise.
  In every case `decoder_version=null`,
  `decoder_version_status=NOT_INDEPENDENTLY_ATTESTED` and
  `indexed_digests_rehashed=false`.
- A source ref repeated **within one capture step** is rejected with
  `ValueError`, not counted as independent corroboration or automatically
  deduplicated. A single original ref may still be legitimately used by
  multiple distinct capture steps, with no inferred canonical association.
  The existing viewer validates its projected refs against the original
  indexed evidence and rejects fabricated canonically assigned step IDs,
  promoted digests, approvals and execution grants.

For Agent B's separate editor Phase 2 (#1302 / draft #1307), the optional
static **synthetic-only** display examples live at
`test_fixtures/r7_capture_readiness_authoring_projection_synthetic.json`.
They show one unlocated capture with UNKNOWN and ambiguous NPC identity,
and one conflicting indexed digest with BLOCKED and an unapproved source
expectation. They contain no real captures, usernames, DSP identifiers,
packet bytes, registered capabilities or approved assertions. Consume as
fixtures for an **opt-in, separately validated read-only evidence panel**,
not as a replacement for the existing reviewer-decision envelope.
Both original handoff SHA-256 and indexed projection SHA-256 have different
projection scopes; their agreement cannot prove source-file authenticity.
Agent B owns display, stale-file and selection-race handling; Agent C owns
#1309's schema. No code in these owned surfaces is changed by #1308.

**Do not confuse source association with evidence observation.** A canonical
source-line citation can become an attributed source *claim* only with a
human-reviewed crosswalk to the exact canonical step ID and independently
validated source refs. Neither a capture step, a parsed NPC ID, a source
manifest hash, nor a candidate DSP oracle is an automatic canonical
association or verified gameplay PASS. The local acceptance steps above
remain mandatory for stronger authentication.


**Capture-scope integrity:** an indexed row claimed by a projected
`evidence_ref` must retain the exact enclosing `capture_id`. Even if the
reference string exists in `evidence_map`, a row declaring a different
capture ID is rejected with `ValueError` (never silently joined or
presented as a valid same-capture observation). Two captures may only be
compared using the existing separately reviewable multi-capture comparison
diagnostic; this display adapter never merges their row identities or
creates a new canonical step/source attribution.
