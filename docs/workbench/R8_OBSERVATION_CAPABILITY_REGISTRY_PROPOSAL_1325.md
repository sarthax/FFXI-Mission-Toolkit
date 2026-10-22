# R8 proposed observation capability registry — Agent E for Agent C review

**Status:** DESIGN PROPOSAL ONLY; schema and capability IDs below are provisional until Agent C approves alignment with #1200 (PR #1322) and #1325. **No registry API, runtime lookup, canonical schema change, MCP tool, auto-preflight promotion, DB query, or execution authority is implemented here.**

**Grounding:** Toolkit source-integrated #1310 inventory-v2 and #1311 progression, existing supervisor bearer + disposable-character allowlist, source-only draft #1324 selected jobs, canonical scenario observation labels in `data/testing/test_specifications.json`, and Agent C's separate pending #1322 R8 `catalog_preview`/`preflight_preview` API. The #1322 catalog lists ONLY MOG-09 and INV-OBS-01 as published scenarios; 73 staged drafts are not published executable cases.

## Design principles and two independent readiness axes

A capability descriptor states **what Toolkit source code can express**, not whether the operator's deployed database or client can be observed. Keep these orthogonal:

- `implementation_state`: `SOURCE_INTEGRATED` (on current main), `PR_ONLY` (implemented only on reviewed/unmerged PR), or `NOT_IMPLEMENTED` (no trusted Toolkit readback). This is a repository claim, not an effective-permission grant.
- `deployment_verification`: `UNKNOWN` until separately attested deployed DSP source/schema, actual connector registration, effective SELECT grants and approved character. Only future independent operator evidence can justify a stronger verification state; none are claimed below.
- `readback_availability`: `NOT_EVALUATED` in a static registry; never mark `AVAILABLE` merely because a route is defined. `UNAVAILABLE`, `DENIED` and `INCOMPLETE` are **per-attempt** outcomes, not static provider capabilities.
- `authority`: always `PERSISTED_DB_ONLY` for these readbacks; `LIVE_RUNTIME_UNSUPPORTED` for missing memory/client providers. `client_agreement` and independent `oracle_approval` remain `UNKNOWN` / `NOT_ESTABLISHED`.
- `execution_enabled=false`, `execution_status=NOT_AUTHORIZED`, `task_admission_supported=false` on both registry and every record; discovery never authorizes data access, SQL, a scenario, oracle, runner, import or mutation.

A catalogue GET **must not invoke** supervisor authentication or DB reading just to list descriptors. Sensitive readback endpoints retain their own bearer/character gates. No invented deployed revisions, grants, physical snapshots or completed observations.

## Suggested candidate descriptor (not a new canonical schema)

A proposal for discussion; deliberately separate `required_*_to_attempt` from `effective_*_verified`. Values below are *descriptive fields*.

```json
{
  "capability_id": "toolkit.persisted.inventory",
  "registry_schema": "toolkit-observation-capabilities/proposal-1",
  "source_type": "PERSISTED_DB",
  "implementation_state": "SOURCE_INTEGRATED",
  "readback_availability": "NOT_EVALUATED",
  "deployment_verification": "UNKNOWN",
  "authorization_class": "SUPERVISOR_BEARER_AND_APPROVED_DISPOSABLE_CHARACTER",
  "supported_scope": {"character": "EXACT_ALLOWLISTED_CHARID", "location_ids": [0]},
  "data_source_requirement": ["chars", "char_inventory"],
  "permissions_requirement": "SELECT_ONLY_ON_LISTED_TABLES",
  "effective_permissions_verified": false,
  "limits": {"max_rows_per_page": 100, "max_opaque_extra_bytes_per_row": 4096, "max_extra_base64_chars_per_page": 65536},
  "completeness_contract": "SINGLE_TRANSACTION_PAGE_ONLY; OFFSET_PAGES_NOT_ATOMIC",
  "provenance": {"kind": "persisted_db_not_live_memory", "source_revision": "UNKNOWN", "attested": false},
  "timestamp_requirement": "UTC_OBSERVED_AT_PER_READBACK; LISTING_TIMESTAMP_NOT_OBSERVATION",
  "client_agreement": "UNKNOWN",
  "oracle_approval": "NOT_ESTABLISHED",
  "execution_status": "NOT_AUTHORIZED",
  "execution_enabled": false,
  "task_admission_supported": false
}
```

The inventory byte budget above caps **opaque data payload**, not every HTTP response byte including headers/JSON overhead. Do not advertise an absolute wire-byte cap that code does not enforce.

### Initial proposed records (provisional IDs; never claim stronger authority)

| Provisional capability ID | Implementation in current main | Required source / exact scope | Bounded output and completeness | Source/deployment and client certainty |
| --- | --- | --- | --- | --- |
| `toolkit.persisted.inventory` | SOURCE_INTEGRATED (#1310) | `chars`, `char_inventory`, charid + location 0 | 100 rows/page, 4,096 raw extra/row, 65,536 total base64 chars; one-page scope, no atomic cross-page guarantee | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.mog_safe` | SOURCE_INTEGRATED (#1310) | same tables, location 1 | identical page/exdata limits; empty vs missing character distinguished | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.mog_safe_2` | SOURCE_INTEGRATED (#1310) | same tables, location 10; distinct slot namespace | identical limits; Safe/Safe2 slots must never be merged | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.named_char_vars` | SOURCE_INTEGRATED (#1311) | `chars`, `char_vars`, 1–50 unique restricted var names | PRESENT zero vs ABSENT; supported subset complete, full progression incomplete | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.key_item_bitmaps` | SOURCE_INTEGRATED (#1311) | `chars.keyitems`, exact charid | expected 896 bytes, owned/seen; NULL/short/long is INCOMPLETE | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.selected_jobs` | **PR_ONLY (#1324, not merged)** | `chars`, `char_stats`; selected mjob/sjob/mlvl/slvl only | one 4-integer persisted record, zero preserved; no unlock inference; full progression incomplete | UNKNOWN / client UNKNOWN |
| `toolkit.persisted.quest_status` | NOT_IMPLEMENTED | source-verified quest status/log required, not provided | UNSUPPORTED, not inferred from char_vars or KI | UNKNOWN |
| `toolkit.persisted.currencies` | NOT_IMPLEMENTED | verified currency field and granularity required | UNSUPPORTED | UNKNOWN |
| `toolkit.persisted.installed_furnishing_effects` | NOT_IMPLEMENTED | installation/effect source unavailable; inventory presence insufficient | UNSUPPORTED/UNKNOWN, never implies active aura | UNKNOWN |
| `toolkit.runtime.entity_claim_state` | NOT_IMPLEMENTED | authoritative map-server runtime identity/claim source unprovided (#1298) | UNSUPPORTED; do not equate nearby client name with server identity | UNKNOWN |
| `toolkit.runtime.instance_door_state` | NOT_IMPLEMENTED | map-server lifetime/door observer unprovided (#1297) | UNSUPPORTED | UNKNOWN |
| `toolkit.runtime.pyxis_state` | NOT_IMPLEMENTED | map-server Pyxis slots and claim observer unprovided (#1299) | UNSUPPORTED | UNKNOWN |
| `toolkit.runtime.temp_items_effects` | NOT_IMPLEMENTED | status effects and temporary items lack authoritative server adapter (#1300) | UNSUPPORTED; client observations cannot fill this gap | UNKNOWN |

All DB providers require `SUPERVISOR_BEARER_AND_APPROVED_DISPOSABLE_CHARACTER`, approved exact charid and **operator-proven effective SELECT-only grants** for the named tables. Unsupported providers have no callable Toolkit reader and must not be advertised as authorized even if a caller presents credentials. The descriptor's `required_data_source` is a *requirement*, not a claim the deployed table exists.

## Relationship to Agent C's scenario catalog/preflight (question for coordination)

Agent C's #1322 `required_observation_capabilities` uses **existing canonical scenario observation labels**, not these proposed Toolkit provider IDs. A separate **explicit, versioned, reviewed mapping** is needed before any preflight consumer evaluates satisfiability. Do not rename canonical scenario observations or auto-register staged cases.

Examples of safe **candidate mapping, not proof of availability**:

- `db_bag` → `toolkit.persisted.inventory` (conceptual provider match; needs observed authorized, complete and contemporaneous data)
- `db_safe` → `toolkit.persisted.mog_safe` (Safe 1; Safe 2 must be separately requested and scoped)
- `stored_furnishings` → **UNSATISFIED**: mere Safe item presence does not prove installed status or effect
- `client_bag`, `client_safe`, `client_key_items`, `gm_active_ki`, `gm_aura`, `session` → **UNSATISFIED BY TOOLKIT DB PROVIDERS**; independent local client/GM/runner evidence remains separately gated
- `toolkit.persisted.key_item_bitmaps` does **not** fulfill `client_key_items`, and `toolkit.persisted.selected_jobs` does not prove an unlocked job or game capability.

**Requested Agent C decisions (before implementation):**
1. Keep registry IDs internal to Toolkit or map to canonical observation strings via explicit `observation_provider_links`? Which component owns the mapping and version?
2. Should #1322 return capability *requirements* only, with a separate R8 read-only metadata endpoint for descriptor discovery, or embed non-authoritative registry summaries in preflight? No shared interface should be merged before this choice.
3. Keep `implementation_state` and `deployment_verification` as independent enums; what exact vocabulary aligns with existing `DECLARED/UNKNOWN/BLOCKED` without allowing a static listing to promote a requirement?
4. What size, pagination and redaction limits will a registry endpoint need? Suggest maximum 32 fixed descriptors per page, deterministic sort and opaque page cursor; this is **not implemented**.
5. Who owns lifecycle of deployed proof? The observation owner can describe required grants, but DSP #59/source attestation, operator grants, independent client agreement and #1198 oracle authority require external evidence and independent review.

## Proposed offline validation after Agent C contract agreement

- Registry is deterministic with stable version, sorted IDs, no duplicate IDs, bounded page count and no ambient time-derived `observed_at` in static listings.
- Every implemented DB entry lists precisely its deployed uncertainty and required auth, table grants and limits. An unmerged #1324 entry stays PR_ONLY until **actually merged**.
- Unsupported providers never appear `AVAILABLE`, `AUTHORIZED`, `COMPLETE` or as fulfilling scenario observations.
- Check `db_bag`/Safe conceptual mapping but ensure no preflight `READY` or automatic authorization, and a client evidence ID cannot be fulfilled by DB evidence.
- Unknown/denied/empty/partial/conflicting and stale snapshot vectors remain distinct; source SHA or grant supplied by a caller stays unverified.
- No SQL, network, filesystem mutation, MCP action or process spawn during catalog enumeration. No canonical spec or runnable catalog modification.
- Reuse Agent C's `R8 Read-Only Catalog Preflight` test idioms after schema owner agreement, rather than creating a competing R8 shared contract.

**No new shared endpoint, runtime adapter or synthetic schema fixtures are added by this proposal.** Agent C must review the design before any implementation PR; #1324 release is independently gated under #1296. Source-only readiness is not deployed readiness or scenario execution permission.
