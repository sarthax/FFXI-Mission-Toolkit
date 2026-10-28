# R8 #1325 — MCP-safe Scenario Discovery: bounded read-only contract

**Status: PROPOSED / OFFLINE CONTRACT, NOT AN INSTALLED TOOL.** Issue #1325
ASI-1/ASI-2. Parent #1197; dependencies #1200, #1198, #1255, #1201,
#1202, #1302, #1313; XIHeadless #105/#110. This document does not
authorize a live Toolkit supervisor tool, a proposal writer, oracle approval,
MCP execution or a Headless schema change.

## 1. Current code, ownership and dependency gate

- Toolkit local supervisor already exposes **read-only**
  `/api/supervisor/*` FastAPI endpoints with
  `operation_id="supervisor_*"`. Every operation calls
  `supervisor._authorize(Authorization: Bearer ...)`, requiring
  `MISSION_TOOLKIT_SUPERVISOR_TOKEN` (minimum 32 characters, constant-time
  comparison). Its scoped OpenAPI endpoint exposes bearer security and
  filters out unrelated application paths. Extend **this existing gateway**
  only after an independently reviewed implementation; do not register an
  alternate MCP server or expose ordinary unauthenticated catalog routes
  to an agent. A model never receives the token.
- Existing #1322 (head `8ac6362f740bd6eaf08e2ac2bc9106e6cec36b08`)
  implements separate, **unmerged at this decision**,
  `GET /feature-testing/r8/catalog` and `GET
  /feature-testing/r8/preflight/{feature_id}/{case_id}`. The safe
  implementation should consume the reviewed #1322 pure catalog/preflight
  functions **after owner-authorized merge**, never copy their schema,
  claim that the proposal makes them authoritative, or duplicate the
  runner. A published MOG-09 fixed local-operator runner remains
  `execution_status=NOT_AUTHORIZED`; INV-OBS-01 remains design-only;
  gardening and the 73 staged domain cases are **NOT_RUN**, not promoted.
- Existing canonical v1 specs and optional Contract v2
  `source_attribution_report` are the read model.
  `sources[]` is an unassigned declaration unless
  `contract_v2.source_associations[]` explicitly identifies a case
  or **exact canonical** step. Oracle-linked and parameter-identity
  references are separate candidate provenance, **not** direct step
  attribution or normative expected values.
- Imported Toolkit v1 records are local historical assertions, not
  independently authenticated DSP/client truth. Optional capture
  readiness #1308/#1315 is **NONCANONICAL**; never automatically
  crosswalk indexed capture step IDs or assert a source byte rehash.
  `XIHeadless #105` is an **unapproved execution** wire proposal,
  unrelated to the **read-only** Toolkit discovery contract below.

## 2. Proposed MCP/OpenAPI method surface (NOT ROUTES YET)

Use one existing bearer-authenticated local loopback gateway. Suggested
operation IDs are aligned with current `supervisor_*` convention; their
exact names remain proposed for Agent A/B/D sign-off and must not
collide with any installed tool. **All routes use GET only.**

| Suggested `operation_id` | Proposed local GET route | Bounded inputs, source and output |
| --- | --- | --- |
| `supervisor_scenario_list` | `/api/supervisor/scenarios` | `feature_id?`, `runner_class?`, `limit=20`, `cursor?`; **published canonical cases only** from #1322. Planning-only features returned as separate `feature_links`, never scenario objects |
| `supervisor_scenario_get` | `/api/supervisor/scenarios/{feature_id}/{case_id}` | Exact canonical identity plus `expected_sha256?`; v1/v2 version and immutable local serialization digest, limited validated presentation, runner, permissions, unknowns; mismatch ⇒ **BLOCKED** not fallback |
| `supervisor_scenario_revision` | `/api/supervisor/scenarios/{feature_id}/{case_id}/revision` | `base_spec_sha256`, `local_definition_sha256`, optional v2 pins and scoped declared digests with algorithm/authority labels; no arbitrary source file reads |
| `supervisor_scenario_sources` | `/api/supervisor/scenarios/{feature_id}/{case_id}/sources` | Explicit case/step `source_refs` and separate unassigned, identity, oracle candidate references; max **50** declared sources, no forged crosswalk |
| `supervisor_scenario_coverage_gaps` | `/api/supervisor/scenario-coverage-gaps` | `feature_id?`, `limit=20`, `cursor?`; published vs planning-only, unapproved oracles, missing readbacks/capabilities, `UNKNOWN/BLOCKED/NOT_RUN` with explanation |
| `supervisor_scenario_preflight` | `/api/supervisor/scenarios/{feature_id}/{case_id}/preflight` | **No caller-supplied authority/lease**; #1322 advisory pure preview (UNKNOWN/BLOCKED), explicit missing dependencies; never submit |
| `supervisor_scenario_evidence_summary` | `/api/supervisor/scenarios/{feature_id}/{case_id}/evidence-summary` | `limit<=10`, `cursor?`; count and recent **redacted** historical imported evidence, attempt completeness and oracle authority UNKNOWN, NO raw items/chat/paths; unconfigured/unavailable ⇒ UNKNOWN not empty “zero evidence” |
| `supervisor_scenario_change_impact` | `/api/supervisor/scenarios/{feature_id}/{case_id}/change-impact` | `source_revision?`, `snapshot_digest?`; **pinned/reviewed source** associations only; if no matched reviewed Git diff or deployed revisions, result UNKNOWN with reasons, not speculative code-impact certainty |

Scenario keys are stable **`feature_id+case_id`**, not a Headless
`operation_id`, a captured step alias, or the position of a staged
domain draft. A version reference is the canonical outer
`schema_version:1`, nullable optional v2 `contract_version:2`,
and `local_definition_sha256` of compact sorted ASCII-escaped JSON.
That digest is **local serialization only**, not an independently
rehash-verified physical source or deployed build SHA. Expected
digest mismatches return an explicit **BLOCKED revision conflict**.
No arbitrary path, glob, shell, source checkout, internet URL or SQL
parameter is supported by these methods.

## 3. Common response envelope: `toolkit-r8-scenario-discovery/1`

The **sample response** is a bounded **presentation contract** for
Toolkit-owned scenario discovery, **not** `xi-test-execution` submit,
status, cancel, operation evidence or an importer format:

```json
{
  "contract": "toolkit-r8-scenario-discovery/1",
  "tool": "supervisor_scenario_get",
  "status": "UNKNOWN",
  "scenario": {
    "feature_id": "moghancement",
    "scenario_id": "MOG-09",
    "schema_version": 1,
    "contract_version": null,
    "local_definition_sha256": null
  },
  "authority": {
    "execution_status": "NOT_AUTHORIZED",
    "execution_enabled": false,
    "task_admission_supported": false,
    "independent_verification": "NOT_ESTABLISHED",
    "oracle_approval": "NOT_ESTABLISHED"
  },
  "data": {},
  "pagination": {
    "limit": 20,
    "next_cursor": null,
    "has_more": false
  },
  "unknowns": ["independent_oracle_authority"],
  "provenance": "DECLARED_OR_IMPORTED_UNVERIFIED"
}
```

Envelope **must** have exactly the required keys above; scoped
tool-specific `data` is separately allowlisted and size bounded.
`status` is `OK|UNKNOWN|BLOCKED|UNSUPPORTED` and is a discovery
diagnostic, **never a gameplay verdict**. A synthetic sample can
illustrate a shape with missing digest as null, but a production
implementation may return `OK` only for structurally valid metadata,
not authenticated client/server truth. All discovered scenarios,
including MOG-09, contain the same denied-authority object.

### 3A. Normative `data.recent[]` item schema (evidence summary)

Applies only to `supervisor_scenario_evidence_summary`. `data.recent` is a
list of **at most 10** items (also bounded by `pagination.limit`); each item
has **exactly** these fields and no others (unknown fields are rejected):

| Field | Rule |
| --- | --- |
| `ref_id` | String, 1-120 printable ASCII characters (`!` through `~`), **no whitespace**; colons are **allowed**. Own `REF_ID` pattern `[!-~]{1,120}`; it is deliberately **not** the identity `KEY` pattern (which forbids colons). Same bounds as #1329 `scenario_evidence_ref_v0_NONCANONICAL.ref_id`, whose synthetic vectors start `evidence:synthetic:`. A display string only: never authentication, a path, or an executable locator |
| `recorded_verdict` | `null`, `PASS`, `FAIL`, `PARTIAL` or `UNKNOWN`; an imported/recorded label, never independent verification |
| `attempt_completeness` | `COMPLETE`, `PARTIAL` or `UNKNOWN` |
| `excerpt` | Short bounded human text, 1-200 printable ASCII characters (space allowed, no control characters/newlines), sanitized and redacted; no raw chat, paths or account data |

**Identity mapping with #1329.** In this contract the envelope key
`scenario.scenario_id` is the **canonical** case identifier for joins, with
`feature_id`. #1329 `scenario.case_id` carries the **same value** and maps to
`scenario_id` by exact string equality (`feature_id` equal and
`case_id == scenario_id`); no case folding, trimming or fuzzy matching. Any
disagreement is `BLOCKED`, not a best-effort join. Items do not repeat the
scenario identity; it is taken from the envelope. The #1328
`failure_evidence_refs` mapping to this `ref_id` is **not yet checked** and
remains a separate review item.

### Identity, security, bounds and deterministic paging

- Service scope: local loopback (existing supervisor gateway only).
  Require configured bearer authentication **before** checking whether
  a scenario exists; unauthorized returns generic 403 with no catalog,
  DB path, account, query, source data or revision hint.
- Strings (feature/case/query) 1–120 chars, ASCII
  `[A-Za-z0-9][A-Za-z0-9_-]*` for canonical identity fields; reject
  traversal, controls, unapproved URL schemes and invalid Unicode
  identifiers. The present published two-case catalog is the maximum
  authoritative surface until #1322 merges.
- Default page 20, hard maximum 25 and **no unbounded offset**.
  Cursor should be opaque/authenticated and bound to filters, the
  sorted `(feature_id,case_id)` tuple, snapshot digest and
  publication epoch. Expired or tampered cursor ⇒ **BLOCKED**; never
  silently restart at page 1. When listings change, invalidate rather
  than skip/duplicate records.
- Per-envelope **65,536 UTF-8 bytes** maximum, per detail spec **32,768
  ASCII-escaped bytes** (matching canonical draft storage bound),
  declared sources max 50, evidence summaries max 10, per returned
  human summary max 500 chars. Reject oversized responses **before**
  serialization to the tool client (413 or bounded typed BLOCKED).
- No raw SQL, user-supplied repository file path, account identifier,
  character ID, secret, bearer echo, local absolute path, unrestricted
  evidence blob, invented link to client DAT, or external URL fetch.
  Do not copy live captures or unredacted exception messages to output.
- Read services must be **side-effect-free**: no POST/PUT/PATCH,
  filesystem write, DB initialization, Headless MCP operation,
  character lease, explicit GM/packet command, proposal promotion,
  oracle approval, permission change, or execution dispatch. Historical
  evidence summaries require separately approved, bounded, **SELECT-only**
  existing result access and must report UNKNOWN if unavailable.
- Record response/operation ID and a sanitized server-side audit
  event *if that later infrastructure already exists*. This design
  does not authorize creating writable audit stores as a dependency
  of a read call.

## 4. Separate provenance and change-impact semantics

Evidence summary provenance has **three separate states**:
`recorded_verdict` in imported Toolkit v1; optional reevaluation
of *runner-supplied* observations; and `independent_verification`
(always NOT_ESTABLISHED unless separately attested by future #1198/#1202).
A historical recorded PASS must be labeled recorded/imported and never
advertised as a verified gameplay PASS. Missing evidence is
`UNKNOWN/NOT_AVAILABLE`, not factual “no historical runs.”

Source revision and change-impact findings may be listed as
`CANDIDATE` only when a reviewed source reference, canonical step
link and exact reviewed diff/revision exist. Neither a changed file
name nor nearby/captured step ID proves source-to-step causality.
An unassigned source, stale fingerprint, missing deployed revision or
absent reviewed diff yields `UNKNOWN` or `BLOCKED`, with a citation
that identifies **which authority is still missing**. Do not
overstate model-generated “confidence.”

## 5. Synthetic offline acceptance and negative cases

`test_fixtures/r8_asi_read_discovery_contract_synthetic.json`
illustrates bounded responses and seven required cases: design-only
INV-OBS-01, fixed local operator MOG-09, unsupported observer,
missing approved oracle, stale source association, missing evidence and
mismatched scenario revision. All samples declare
`synthetic:true` **outside** the wire `response`; no fixture is
an imported result or proof of live Headless gameplay. The offline
pytest test checks the envelope and **denied runtime authority**,
source/ref scope, status classification, stable paging bounds,
forbidden fields, oversized payloads and stale revision conflicts.

## 6. Concurrent ASI contract ownership — explicit nonduplication decision

This read envelope and method inventory must **not** fork the concurrent
proposal, evidence or capability schemas. At this design checkpoint:

- **Agent B [#1328](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1328)**
  owns `scenario_revision_proposal_preview_v1_NONCANONICAL`,
  proposal ID/idempotency, selected baseline `base.revision`,
  `base.spec_digest_claim`, bounded before/after change paths,
  duplicate detection and the untrusted preview UI. A proposal's
  `scenario.feature_id+case_id` may refer to a published catalog
  identity, but the canonical catalog's
  `local_definition_sha256` is **not** the same as Agent B's saved
  draft revision and is never a reviewer acceptance token.
  `feature_trace_refs`, `source_refs`, failure and coverage IDs in a
  proposal are opaque evidence **claims** until a reviewed resolver
  independently validates them. Discovery supplies read-only metadata,
  **never** `scenario_propose_revision`, auto-save, reviewed promotion
  or oracle modifications.
- **Agent D [#1329](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1329)**
  owns `scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL`
  with separate run/attempt IDs, imported/reported observations,
  competing or missing readbacks, approved versus candidate oracle,
  source revision, cleanup/terminal and replay/conflict semantics.
  The proposed `supervisor_scenario_evidence_summary` is **only a
  future bearer-authenticated, capped Gateway index/wrapper** over a
  separately accepted Agent D projector; it does **not** define
  an alternative full evidence schema, authoritative verdict or
  Headless v2 import. Agent D's own `scenario_evidence_summary`
  is a provisional conceptual tool name, **not registered**. Use the
  gateway's stricter **10-record / 64-KiB** cap even if a downstream
  read model allows a larger query. #1329 is now merged, but only as a
  **design-only** contract: no evidence projector is implemented or accepted.
  Until a separately reviewed projector and an approved, bounded SELECT-only
  data source exist, the gateway must return `UNKNOWN` rather than fabricated
  zero or facts. The `data.recent[]` item shape is normative in section 3A.
- **Agent E [#1327](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1327)**
  owns the **proposed** observation provider inventory. Canonical
  `observations[]` labels (`db_bag`, `db_safe`,
  `client_safe`, etc.) are not provider IDs. A later,
  reviewed, **versioned static crosswalk** must map exact
  canonical `feature_id+case_id+required_observation_id` to a
  candidate provider descriptor ID. Do not rename existing catalog
  IDs, infer a provider from matching strings, silently map SQL
  persisted snapshots to client-observed capability, or promote
  `SOURCE_INTEGRATED`/`PR_ONLY` to deployed/approved
  `READY`. Until a provider is independently confirmed
  deployed and authorized with compatible scope, preflight remains
  UNKNOWN/BLOCKED and not executable. Only Agent E may finalize
  descriptor/enum vocabulary; Agent C owns canonical observation
  label mapping in a separate reviewed contract after #1327.
- **Agent A** releases each PR independently with exact-head CI,
  no overlapping edits and explicit owner merge authorization.
  No one derives a canonical source step association or
  Headless execution permission from these read/proposal/evidence
  design documents.

These interfaces deliberately remain **a thin discovery envelope**
over current Toolkit-owned canonical objects and separately reviewed
noncanonical projections. They do not create a competing
`xi-test-execution` lifecycle or change the canonical v1/v2 schema.

## 7. Ownership/milestones; not merged by this contract

1. **ASI-1 / #1322 (#1200):** Agent C final release review,
   owner-authorized merge of GET-only catalog/preflight. Until merged,
   #1325 consumes no production endpoint from this PR. Current #1322
   independent Agent A review and owner approval remain separate gates.
2. **ASI-2a / this design:** Agent C reviews the eight read shapes,
   failure semantics, strict bounds/authentication and test fixtures
   with Agent A, Agent B and Agent D. **No runtime routes yet**.
3. **ASI-2b / bounded implementation:** after #1322 is merged and
   gate decisions are accepted, implement **only** published catalog,
   exact detail/revision/sources and preflight with new
   `supervisor_*` GET IDs under existing Bearer gateway. Reuse
   canonical validator/projections, no duplicate spec parser.
   Evidence summaries and change impact remain gated independently
   on #1202/#1198 evidence authority and a reviewed Feature Trace
   source-change index; return explicit UNKNOWN until backed by
   an accepted data source.
4. **ASI-2c / future proposals:** Agent B owns proposal diff/review
   UI in Scenario Developer. No canonical catalog save,
   `scenario_propose_revision`, oracle redefinition or runner
   permission mutation in this PR. Agent D owns noncanonical
   evidence provenance and reviewed sidecar validation.
5. **ASI-3 onward:** Human-reviewed promotion through existing
   validator/Git PR, with explicit approval for normative oracle
   and any future execution privilege. XIHeadless #105/#110
   execution transport is separate and still unapproved; do not
   implement submit/status/cancel here.

**Not tested/authorized:** live MCP discovery registration, actual
Bearer gateway access from an agent, external sources/client/DSP
revision attestation, independent oracle truth, client observations,
unrestricted source-index crawling, file/DB changes, or supervised
gameplay. Those require separate local acceptance and project gates.
