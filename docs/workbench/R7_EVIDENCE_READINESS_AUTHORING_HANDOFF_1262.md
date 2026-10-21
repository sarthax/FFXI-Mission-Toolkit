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
