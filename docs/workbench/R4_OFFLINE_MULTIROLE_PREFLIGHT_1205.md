# R4 #1205 — Synthetic offline multi-role preflight and coverage projection

**Scope:** pure, non-executing Toolkit adapter and pytest tests. This is **not a new scenario catalog, not a UI route and not an approved XIHeadless task schema**. See [Toolkit #1205](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1205), [existing R8 GET-only catalog PR #1322](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1322), [XIHeadless #105](https://github.com/sarthax/xiheadless-dsp/issues/105), [Headless multi-bot #51](https://github.com/sarthax/xiheadless-dsp/issues/51), and [oracle model #1198](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1198).

## Contract and safe presentation

`src/workbench/server_admin/feature_testing/offline_multirole_preflight_1205.py` exports `offline_role_preflight(definition, claims=None)`. Its only accepted schema name is `toolkit-r4-synthetic-role-preflight/1` — an isolated Toolkit-local *synthetic fixture schema*, **not** the unapproved `xi-test-execution` protocol. A definition has exact keys `schema`, `feature_id`, `scenario_id`, `required_role_kinds`, `roles` (1–6) and `checkpoints` (1–24). Roles provide a symbolic ID, kind (leader/healer/dps/tank/support) and required symbolic capabilities. Checkpoints specify one or more role IDs, acyclic prerequisite checkpoint IDs and a symbolic oracle ID. Each role requires **one unallocated, hypothetical lease unit**. No account names, character IDs, server values or packet data appear in inputs.

Untrusted optional `claims` may declare available role kinds, pool slot count, reported capabilities, lease status, cleanup status and oracle coverage states. They are not runtime observations; claims are not authenticated and cannot grant admission. A missing claim returns `UNKNOWN`; a claimed missing healer, insufficient pool, unknown checkpoint dependency/schema, unavailable lease, incomplete cleanup or explicitly missing oracle returns `BLOCKED`. Claimed complete cleanup/available lease/covered oracle is only `DECLARED`, never observed completion. Even when every optional claim matches, the aggregate `preflight_state` is `UNKNOWN`, **never** `READY` or `PASS`.

The deterministic output includes role needs, an ordered directed role→checkpoint and checkpoint dependency graph, checkpoint oracle coverage, prerequisite checks, explicit blockers/unknowns and feature/scenario **reference identifiers**. These are metadata cross-links, not fabricated active hyperlinks or a second R8 catalog entry. Every response, including rejected schema, retains:
```json
{
  "execution_status": "NOT_AUTHORIZED",
  "execution_enabled": false,
  "task_admission_supported": false,
  "lease_acquisition_supported": false,
  "persisted": false,
  "claims_authority": "UNVERIFIED_PREVIEW_ONLY",
  "oracle_authority": "NOT_ESTABLISHED",
  "observed_gameplay_verdict": "UNKNOWN"
}
```
The returned `local_definition_sha256` hashes only synthetic JSON serialization and **does not attest canonical scenario revision, actual HEADLESS/DSP/Toolkit commits, installed build, pool lock, physical cleanup or oracle origin**. Unsupported versions and malformed fields fail closed with a bounded `offline_schema` blocker; the model neither supplies nor assumes #105 action IDs, task lease tokens, authoritative server state or producer signatures.

## CI and acceptance

Focused workflow: `.github/workflows/r4-offline-multirole-preflight.yml`; executable test: `test_fixtures/test_offline_multirole_preflight_1205.py`. Tests are labeled **synthetic** and check:

- Single leader versus leader/healer/DPS checkpoint graph and prerequisite ordering.
- Missing healer, pool slots 0–2 for a three-role case, missing symbolic capability, oracle marked missing, lease unavailable and cleanup incomplete → BLOCKED.
- Unknown oracle, lease and cleanup → UNKNOWN, even if other claims are covered. All positive-looking claims remain DECLARED and no execution or gameplay PASS is projected.
- Unsupported upstream or local schema, extra executable field, duplicate IDs, role/checkpoint ID collision, unknown checkpoint or role dependencies, DAG cycle, bad version, invalid bool/numeric pool claim, unknown oracle status and unexpected nested data → BLOCKED.
- Input left intact, deterministic projection and no disk writes.

This does **not** modify the existing #1200/#1322 R8 catalog, current routes/templates, own #1399 offline evidence importer, #1339 personality consumer, Headless multi-bot process, pool manager or E's #1201 lifecycle UI.

## Future owner gates (BLOCKED / NOT_RUN)

1. **Headless protocol:** #105 and multi-bot #51 owners must approve role, lease, checkpoint, oracle and cleanup identity/wire contract first. This local model is not a converter to that protocol, cannot become a READY label or an MCP task.
2. **Catalog/UI:** after #1200/#1322 read-only source release and #1198 oracle scope are reviewed, the original Toolkit owners decide how to attach this projection to a feature/scenario browser. Avoid linking to nonexistent routes or turning R8 advisory checks into execution.
3. **Observed evidence:** authenticated physical role availability/lease ownership, pool quarantine and safe logout, oracle coverage and source revision must be observed by an authorized isolated local agent using disposable characters; no live tests were performed here.
4. **Release:** require exact-head targeted+Workbench/Src regression CI, one independent code review and explicit Toolkit owner merge permission. Do not call an offline unit pass “multi-bot accepted”.

No privileged API, SQL mutation, transport, filesystem storage, process launch, MCP request, character allocation, Headless/DSP/GM/client connection, or gameplay.
