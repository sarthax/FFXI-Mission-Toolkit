# R7 Canonical Contract v2 — explicit source attribution decision

**Status:** DRAFT / proposed interface; awaiting Agent B + Agent D confirmation,
independent source-schema review, and owner-authorized merge. This file does
not authorize editing the Scenario Developer or Evidence Reviewer directly.

**Baseline:** Integrated Toolkit main `972ff6fa` (merged R6 canonical #1285,
editor Phase 1 #1283, reviewer diagnostics #1287 and nine staged domain JSON
designs). Issue #1302; parent #1197; schema owner #1259.

## Decision: one additive optional source-association collection

The accepted v2 namespace retains its **six original mandatory keys**:
`contract_version`, `sources`, `parameters`, `oracles`,
`step_requirements`, and `fingerprints`. Optional
`contract_v2.source_associations` is the **only** proposed new key. Omission
preserves all old v1 and v2 documents, with `UNKNOWN` attribution.

```json
{
  "contract_v2": {
    "source_associations": [
      {
        "scope": "case",
        "target_id": null,
        "source_refs": ["existing-source-ref"]
      },
      {
        "scope": "step",
        "target_id": "existing-canonical-v1-step-id",
        "source_refs": ["existing-source-ref"]
      }
    ]
  }
}
```

The snippet illustrates **the added optional field only**, not a complete
canonical `contract_v2` envelope. Save remains subject to the full canonical
validator, source-list bounds, JSON duplicate-key rejection and the existing
32-KiB SQLite ASCII-escaped JSON storage limit. `base_spec_sha256` continues
to hash **v1 core only**, not the descriptive v2 namespace.

| Relationship | Exact canonical carrier | Scope/presentation |
|---|---|---|
| Source citation belongs to the **case** | `source_associations[{scope:"case",target_id:null}].source_refs` | Explicit **case citation claim**, never applies to every step |
| Source citation belongs to an individual **step** | `source_associations[{scope:"step",target_id:<v1 step id>}].source_refs` | Explicit **step citation claim**, not an approved oracle or observation |
| Source citation supports an **identity candidate** | Existing `parameters[].source_refs` and `parameters[].binding_state` | Named candidate; no automatic association to step; ambiguous/unresolved never selected |
| Source citation supports an **expected-value candidate** | Existing `oracles[].assertion_id` + `oracles[].source_refs`, with `confidence="candidate"` | Only for an existing v1 assertion and validated normative source class. No new v1 `assertions[].expected` value is inferred |
| Missing/uncertain relationship | No explicit source association | `UNKNOWN` / `UNASSIGNED`; do not infer from `steps[].evidence_refs`, assertion identity, display order, or staging aliases |

**Validation:** Optional list max 100. Each row has exactly
`scope,target_id,source_refs`; scope is only `case` or `step`. Case
requires null target. Step requires exact **existing v1 step ID**. Each
target/scope pair may appear at most once. Source refs must be a nonempty,
unique subset of `sources[].ref`. Reject extra keys, duplicate targets,
unresolved/duplicate source refs, malformed types, and conflicting
revision/SHA-256 pins for the same repository/path **within one target**.
Different source spans at one repository revision remain valid. No position-
based or fuzzy matching is performed. All original `sources[]` and
`source_associations[]` survive `serialize_spec`/`deserialize_spec`
without normalization, truncation or auto-correction.

### Consumer contract freeze (proposed; B/D acceptance pending)

**Canonical source identity** is `contract_v2.sources[].ref` (one unique ID
*within this specification*), not a global source ID or source-content digest.
It resolves to exactly one canonical source entry with
`repository/path/line_start/line_end/revision/classification/sha256`.
`revision` is a claimed 40-hex commit or null; `sha256` is a claimed
64-hex content digest or null. Metadata equality and source IDs **do not**
authenticate original bytes or deployed engine versions.

**Four distinct display scopes** must remain separate:

1. `case`: optional `source_associations[{scope:"case",target_id:null}]`;
   source claims apply only to the case document, **not** to any step.
2. `step`: optional `source_associations[{scope:"step",target_id:step.id}]`;
   the ID is exact and case-local. `source_refs` must identify canonical
   `sources[].ref`; repeated refs, unknown step IDs, and multiple
   associations for the same step are invalid. No positional linking.
3. `identity`: the existing `parameters[].{name,kind,identity,namespace,
   zone_id,binding_state,source_refs}`, which does **not** infer the step on
   which this parameter is used. `ambiguous` and `unresolved` must keep
   `identity=null`; `independently_source_verified` is only the
   declared pinned-source confidence claim already defined by canonical v2.
4. `oracle`: existing `oracles[].{assertion_id,oracle_type,source_refs,
   confidence}`. `assertion_id` must match a real canonical v1 assertion,
   and a `source_rule/source_literal` is still an *expected-value candidate*,
   not approved normative evidence. `steps[].assertion_ids` can explicitly
   identify an assertion-linked oracle, **not** a general direct step citation.

**Optionality:** `contract_v2` is optional for legacy v1. When it is
present, all six pre-existing required v2 fields remain mandatory.
`source_associations` is optional; omission and `[]` both yield
`UNKNOWN` scope relationships. An association row, when present, requires
all three keys; null or empty `source_refs` in a row is rejected. Do not
auto-insert empty associations on legacy save or clone.

**Cross-case protection:** `scope:"case",target_id:null` refers to the
**current canonical v1 document**; step IDs and source ref names have *no
global meaning*. Copying association metadata to a different case while
renaming its steps must fail on dangling step links. Copying to a different
case with identical step IDs **cannot be authenticated by ID equality**:
if a previously pinned `fingerprints.base_spec_sha256` no longer matches
the v1 core, `compatibility_report` returns `BLOCKED`; if the pin is
absent, the result stays `UNKNOWN` and independent verification remains
`NOT_ESTABLISHED`. The read-only association helper describes what the
document *claims*, not whether a copy has been approved. Agent B must
display compatibility status separately and prevent unsafe silent repinning.

**Revision mismatches:** same repository/path with different
`revision` or `sha256` **within a single association target** is
invalid. Conflicts across separately scoped, original source declarations
are not magically reconciled; they need a human source/revision review and
the normal fingerprint compatibility gate. A supplied mismatch is
`BLOCKED`, missing independently supplied evidence is `UNKNOWN`, and
`MATCHED_PINNED_ONLY` proves **only structural agreement**, not a
reviewed source-to-step fact, independently verified identity, oracle approval,
or execution authorization.

**Persistence:** `validate_spec` must accept legacy v1 and old optional
v2 documents byte-for-byte at the field level. Explicit associations are
JSON-serialized and parsed with stable IDs, no inferred relationships or
normalization. Duplicate JSON keys are rejected, and both compact UTF-8 and
ASCII-escaped SQLite 32 KiB size constraints continue to apply. Metadata
alterations never silently change `base_spec_sha256` (hash of v1 core only).

**Agent D's producer boundary:** `capture_readiness_authoring_projection_v1_NONCANONICAL`,
its original `indexed_evidence_provenance` and both projection SHA-256
claims must remain *separate* from canonical source associations. A capture
reference alone is neither a canonical source ref nor a reason to populate
`step`, `identity`, or `oracle` associations. A future reviewed crosswalk
must validate canonical source file/revision, exact step/assertion identities,
namespace/zone and independent provenance before authoring either v2 link.
No automatic import, oracle approval, capability grant or dispatch.

**Read-only projection helper:** `source_attribution_report(spec)` first
invokes the canonical validator and emits explicit case and per-step source
references. It emits `state="UNKNOWN"` when no exact link exists, otherwise
`state="EXPLICIT_CITATION_CLAIM"`; always emits
`independent_verification="NOT_ESTABLISHED"`,
`oracle_approval="NOT_ESTABLISHED"`, and `execution_enabled=false`.
`EXPLICIT_CITATION_CLAIM` means the author placed a reference, **not** that
the source content hash was independently rehashed or gameplay observed.

### Rejected alternatives

- **Do not add `source_refs` to v1 `steps[]`:** changes established v1 step
  keys and risks confusing authoritative client observation `evidence_refs`
  with repository source citations.
- **Do not add `source_refs` inside canonical `step_requirements[]`:**
  its existing strict fields are per-step permission/readback declarations.
  The noncanonical domain adapter has such a field, but it is not a canonical
  field, and copying it would silently infer acceptance of staging aliases.
- **Do not attach every case source to every step:** it misrepresents evidence,
  especially with multiple cited methods and contradictory revisions.
- **Do not turn scoped attribution into `source_rule` or `source_literal`
  oracle approval:** existing assertion identity and normative source class
  gates remain authoritative; Agent D expected candidates are still
  noncanonical without a reviewed assertion/source crosswalk.

## Domain and Evidence Reviewer interoperability

All nine integrated domain JSON documents contain **73 design-only cases**,
still outside `data/testing/test_specifications.json`. Their
`oracle_sources/oracle_refs/source_refs` and `readback/required_readback`
aliases are preserved by `scenario_contract_v2_adapters.project_domain_case`
as **NONCANONICAL** metadata. This draft does **not** map them into new
canonical `source_associations`: human acceptance must confirm the case and
step IDs, original citation, pinned revision, and intended relationship first.

Agent D's `capture_readiness_authoring_projection_v1_NONCANONICAL` remains
a separate read-only sidecar. Its `EXACT` is no more than a uniquely scoped
source-record match, `INFERRED` remains candidate/unresolved,
`AMBIGUOUS` null identity, and expected candidates are not approved. A
capture index SHA-256 is not the original source file hash. Source provenance
conflicts should appear as `BLOCKED`; unavailable independent source and
runtime evidence as `UNKNOWN`. `MATCHED_PINNED_ONLY` still means pins
compare as supplied, not authenticated or runnable.

## Acceptance and ownership

Focused offline synthetic tests cover legacy MOG-09/INV-OBS-01 without v2;
legacy optional-v2 shape; scoped case versus step links; explicit
source-backed identity/oracle candidates; duplicate and nonexistent refs;
stale step ID; duplicate target; contradictory source digest or revision;
JSON lossless round-trip; UNKNOWN/BLOCKED fingerprint states; denied
mutations; existing Unicode size bounds; and nonpromotion for all nine domain
families.

**Agent B #1307:** no edits to editor JS/routes or to this current Phase 2 PR.
Keep existing explicit `assertion→oracle→source` display behavior. Do not
consume `source_associations` until the schema draft passes review and merges.
Afterwards, present case, step, identity and oracle citations in **separate**
read-only scopes. Preserve all existing save/preview/dirty-race safeguards.

**Agent D #1287:** no edits to reviewer, capture parser, or sidecar. A future
source-to-canonical producer crosswalk must independently validate original
source bytes, identity namespace/zone, assertion IDs and trusted operator
approval. This change provides **no** physical authentication.

**Agent E #1294:** reuse merged nine-domain validator and matrix. This
optional schema provides no permission for bulk domain import or v1 runner
changes, and GitHub CI cannot attest deployed DSP/client versions, real
source-byte authenticity, or independently observed gameplay PASS.

**Merge gates:** Agent B/D field-name agreement; independent current-head
review; focused Contract v2/Workbench/Src Layout CI; owner authorization.
No local client, DSP server, GM, SQL write, packet, or gameplay operations.
