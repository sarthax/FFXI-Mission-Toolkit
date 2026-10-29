# Mission Toolkit — Headless personality catalog read-only consumer v1

**Issue:** [#1338](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1338)  
**Canonical owner:** [XIHeadless #214 / draft #215](https://github.com/sarthax/xiheadless-dsp/pull/215)  
**Mode:** Read-only JSON bytes → strictly pinned manifest → future browser/list/compare. No Headless/Valhalla access or client/server execution.

## Priority and authority

The owner explicitly prioritizes **Headless and Mission Toolkit as the primary consumers** of a robust, reusable personality system. LSB Trusts are source inspiration; actual Valhalla pet-based Trusts are **a secondary translation target**, not the canonical schema.

Canonical Headless personality profiles are composed from:
- 22 FFXI job-role mappings;
- 21 non-executing personality archetypes across healing, MP management, recipient-aware buffs, BRD/COR/GEO, tanking, skillchain/MB, ranged and pet control;
- 24 source-annotated fact/ability prerequisites, **all requiring actual acceptance**;
- 19 pinned LSB Trust source inspirations, including **sparse/unimplemented examples**.

**Toolkit must never invent new authoritative profiles or overwrite the Headless catalog.** It can provide visualization, comparison, evidence joins, operator questions and export of *suggestions*, never a bypass of Headless's existing `PartyCombat`, `JobKits`, `INavigation`, shared pool or task lifecycle.

## Source pin (candidate, pending Headless review/merge)

| Field | Value |
| --- | --- |
| Canonical repository | `sarthax/xiheadless-dsp` |
| Source file | `docs/personality-catalog/v1/personality_catalog.json` |
| Catalog version | `1.0.0` |
| Review branch | `codex/214-personality-catalog-v1` — draft [#215](https://github.com/sarthax/xiheadless-dsp/pull/215) |
| Source commit | `a025dc71b64c1d7d79319d19159fdedcb5647c01` |
| Git blob SHA-1 | `b0166b818862b5b7996e0b0c3f6d8449240e4474` |
| Acceptance | **GitHub Actions source/schema only, 31 contract tests. No runtime acceptance.** |

The Toolkit implementation `src/workbench/personality_catalog_consumer.py` takes **the raw source bytes passed by an approved caller** and a Git `CatalogPin`. It checks the **real Git blob hash** (size+NUL+bytes), strict version, consumer priority and statuses. It **does not perform an HTTP request** and is not a network connector. A passing blob hash confirms *only exact byte identity to the configured pin*, **not maintainer identity, private-client evidence, trusted gameplay outcomes or user authorization**.

The pin is **temporary until PR #215 passes independent review**. After Headless merges an accepted version, update source commit+blob in a separate controlled PR, rerun tests and review the diff. New catalog versions require corresponding import contract reviews; do not silently fall back to a stale snapshot or copy the JSON into Toolkit's DB as a rival source.

## Read-only first UI contract

The new importer exposes functions (no GUI route or action handler yet):

- `load_pinned_manifest(raw: bytes, pin: CatalogPin)`: fail-closed import, outputs `ReadOnlyCatalog` with original job, profile, capability and LSB inspiration records plus source metadata.
- `list_job_profiles(catalog, job_code)`: a job's **design-option** profile set, eligible roles, source revision and explicit `execution_enabled=False`, `gameplay_verdict=NOT_TESTED`.
- `compare_profiles(catalog, [id1, ...])`: small deterministic profile comparisons with priority, target selectors, symbolic action intent, required fact IDs and **not-verified** evidence. It never runs a decision on actual party data.

Future Toolkit GUI view should show:
1. Job/role filter and profile archetype list.
2. Side-by-side priority/target/fact prerequisite comparison.
3. LSB character inspiration panel with source SHA and **sparse script warning**.
4. Evidence overlay with **DESIGN_ONLY, BLOCKED/UNKNOWN, OBSERVED**, sourced from authenticated Headless/Toolkit scenario evidence. Never mark “compatible with Valhalla” due to a similar LSB script.
5. Optional export of pinned config *metadata* after a separately approved Headless policy resolver exists; no action-execution or GM control button in this read-only page.

These future routes/components are **not implemented here**. Current work is a tested interface boundary to avoid conflicting with active Toolkit R8 and validation features.

## Tests and danger cases

```bash
PYTHONPATH=src python -m pytest -q test_fixtures/test_personality_catalog_consumer.py
```

`.github/workflows/personality-catalog-consumer.yml` runs on GitHub for changes in this isolated slice.

Synthetic tests cover:
- Valid pinned source blob versus modified data (exact byte comparison);
- wrong repo/commit, mismatched version, changed catalog authority/consumer order;
- rejecting runtime-ready, executable and unsupported Valhalla owner-only policy injection;
- rejecting duplicate jobs/profiles, unknown binding, fabricated status, sparse source personality;
- deterministic compare preview, job preview, no command dispatch and preservation of input data.

**Not performed:** actual local Headless bot tests, Valhalla/DSP server tests, packet acceptance, LSB code execution, live profile selection or UI navigation. A GitHub Actions PASS here confirms **input validation only**.

## Owner boundaries and prerequisites

- [Headless #199](https://github.com/sarthax/xiheadless-dsp/issues/199) retains future Headless *runtime* role-intelligence gating. This Toolkit importer cannot make that issue `ready`.
- [Headless #214](https://github.com/sarthax/xiheadless-dsp/issues/214) owns versioning and data definitions.
- [Toolkit #1338](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1338) owns read-only import/display/evidence comparisons.
- [Toolkit #1333](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1333) and active R8 scenario authoring/editor teams retain their file and route ownership; this PR touches none.
- [Valhalla #63](https://github.com/sarthax/darkstar-to-valhalla/issues/63) remains a future source-specific Trust adapter, not a constraint on Headless ally heal targeting.

**No merge without independent review or the owner's authorization.** In particular the first acceptance gate is Headless catalog #215 approval, followed by this pinned Toolkit consumer #1338 integration acceptance.
