# R8 #1200 — Published scenario catalog and advisory preflight

**Mode:** GitHub-only, read-only. **NOT AN EXECUTION INTERFACE.** This
slice implements the first Toolkit-owned, bounded catalog/preflight feature
on top of existing canonical v1 and optional Contract v2 metadata. It does
not implement or approve XIHeadless #105, add a runner, contact MCP, inspect
the live server/client, initiate a lease, create SQL, or persist state.

## Endpoints

- `GET /feature-testing/r8/catalog` returns *only* the published, canonical
  `data/testing/test_specifications.json` specifications. At the time of
  implementation these are `moghancement/MOG-09` (fixed **local operator**
  observation runner) and `inventory_observation/INV-OBS-01` (design-only,
  runner unassigned). The response includes scenario ID, outer v1
  `schema_version`, optional `contract_version`, deterministic **local
  JSON serialization** fingerprint (not source/deployment attestation),
  runner classification, declared observation IDs and precondition notes,
  required authorization class, oracle IDs, nonnormative provenance,
  unverified source claims, and explicit unsupported/unknown fields.
- `feature_links[]` maps these published cases to existing Feature Testing
  feature IDs/names, while linking `gardening` and other domain **planning
  features as `NO_PUBLISHED_SCENARIO`**. It deliberately does not publish
  staged GARD, MOG, VOID, ASLT or other design-only case IDs as runner
  specifications. The 73 staged cases are **NOT_RUN and non-executable**.
- `GET /feature-testing/r8/preflight/{feature_id}/{case_id}` compares
  published metadata with *no external trust claims* and enumerates missing
  requirements. A nonexistent/planned-only scenario returns
  `published_identity:BLOCKED`, not a made-up executable runner.
  Unlike the earlier `/preflight/{feature_id}/{case_id}` local MOG-09
  environment check, this R8 route does **not** read operator environment,
  DB, runner filesystem, credentials, real deployment state, or network.

The pure `preflight_preview(..., claims={...})` helper also supports bounded,
**explicitly untrusted synthetic test claims** for version, deployment SHAs,
observation IDs, oracle IDs, source attribution, character/zone/lease and
operator grant. It never processes a URL, subprocess, SQL query or MCP tool.
Unknown claim fields fail closed; supplied grant, SHA or oracle ID is a
**declaration, not independent authentication**.

## Semantic gates

Each checklist finding is `DECLARED` (a **metadata or untrusted claim
matches**), `UNKNOWN` (not established) or `BLOCKED` (unsupported, missing,
contradictory or unregistered). The aggregate `preflight_state` is
`BLOCKED` for any blocked finding and otherwise `UNKNOWN`, **never READY**.

The preview checks: canonical published scenario, version pin, fixed runner
classification, three deployment revision shapes, required observation IDs,
oracle identifiers and authority, source-to-case/step association (only
explicit canonical Contract v2 `source_associations` count), operator
authorization, character/zone, lease, unsupported mutation, and canonical
base-spec/source fingerprint compatibility. A legacy v1 source with no
`contract_v2` remains UNKNOWN for source provenance even if the fixture
claims a grant. Missing direct source links are never manufactured from
`steps[].evidence_refs`, identity candidates or `oracles[].source_refs`.

**Every response** contains `execution_status:"NOT_AUTHORIZED"`,
`execution_enabled:false`, `task_admission_supported:false`; preview
responses additionally include `persisted:false` and
`claims_authority:"UNVERIFIED_PREVIEW_ONLY"`. Even if all synthetic claims
match, a preview cannot confirm DSP binary/commit provenance, deployed
source bytes, operator effective permissions, independent oracle approval,
lease ownership, or complete client/server readbacks. A future green
external readiness report would still **not be permission to execute**.

## Contract and dependency ownership

- Canonical Contract v2 `source_attribution_report(spec)` is used
  unchanged; citation claims cannot approve an oracle or grant permissions.
  `compatibility_report` identifies stale base specification SHA and
  missing independently verified source/engine revisions.
- The existing operator-only MOG-09 runner and all existing
  `execution_preflight.py`, `execution_cli.py`, importer v1 and database
  behavior remain unchanged. The new GET routes do not enqueue tasks.
- XIHeadless [#105](https://github.com/sarthax/xiheadless-dsp/issues/105)
  `xi-test-execution/1.0.0-draft.1` remains an **unapproved proposal**;
  [#110](https://github.com/sarthax/xiheadless-dsp/issues/110) owns later
  identical-byte offline producer/consumer conformance once approved.
  This response format is a Toolkit **local presentation format**, not a
  competing #105 wire protocol.
- Toolkit [#1198](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1198)
  owns independently approved oracle and observation authority;
  [#1201](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1201)
  owns supervised run/status/cancel only after #105/#47/#49 approval;
  [#1255](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1255)
  owns bounded observation execution after local acceptance;
  [#1202](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1202)
  owns versioned idempotent evidence import. #1197 coordinates final local
  test acceptance. No dependency is implicitly satisfied by this PR.

## Offline acceptance

`test_fixtures/r8_catalog_preflight_cases_synthetic.json` lists twelve
synthetic positive/negative gate vectors: published and unknown scenarios,
missing/incompatible version, unsupported runner, missing deployment,
missing capabilities/oracles, unauthorized mutation, absent source link,
missing operator grant, and unverified matching claims. The pytest
suite checks the two published catalog identities, Gardening planning-only
feature linkage, legacy v1 and explicit v2 association metadata, stale base
SHA rejection, fail-closed unknown fields, GET route-only exposure,
deterministic output and no subprocess/SQL side effects.

**Not verified:** Headless runtime, actual source-byte SHA, local runner
attestation, DSP SQL SELECTs, char pool/lease, client/GM/packet reads,
independently approved oracle, browser integration, and authorized gameplay.
No review or merge grants those capabilities.
