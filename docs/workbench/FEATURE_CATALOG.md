# Feature Catalog v1

The Feature Catalog is the structured inventory of **what the Toolkit exposes**. It is deliberately distinct from the Roadmap (remaining development and validation) and Help (usage instructions).

## Canonical data

`feature_catalog/features.json` is the curated v1 source. Subfeatures use an optional `parent_id` pointing to an existing module record. The loader rejects duplicate IDs, missing parents and direct self-parenting. Parent records and child records may share a module route because a dedicated subfeature deep-link is not always available.\n\nEach record has a stable `id`, `module`, `name`, `summary`, primary `route`, `help` route, `implementation` status and independent `validation` status.

Implementation statuses: `implemented`, `partial`, `research`, `planned`.
Validation statuses: `unverified`, `operator_reported`, `tested`.

A route or source reference does not establish runtime acceptance. The inventory began as a Help-derived seed, **not** an exhaustive module or subfeature census. The catalog is separate from Feature Trace's graph schema.

## GUI

`/feature-catalog` renders searchable/filterable records. Help and Roadmap link to it. The catalog is listed in the Home / Project shell navigation and linked from Help and Roadmap.

## Adding a feature

1. Add a unique slug to `feature_catalog/features.json` with a grounded route and Help destination.
2. State implementation and validation separately; use `unverified` unless reproducible acceptance evidence exists.
3. Run `python test_fixtures/test_feature_catalog.py` and `python test_fixtures/test_help_route_inventory.py`.
4. Keep the Roadmap limited to work remaining and link it to the corresponding capability when appropriate.

## Next milestones

- Reconcile **all** Help sections, sidebar pages and route inventory against the catalog; classify module versus subfeature granularity.
- Add explicit provenance references to merged PRs and source/test evidence for every capability.
- Add automated drift reporting (uncataloged routes, missing Help, outdated descriptions) without treating every API endpoint as a user-facing feature.
- Introduce dedicated sidebar navigation and optional graph linkage after the catalog passes acceptance.

This v1 does not scrape Help automatically or declare every route to be a capability.

## Coverage diagnostics

The Catalog page now shows an expandable **Coverage audit**. `workbench.core.services.feature_catalog_audit.audit_catalog()` compares global Help's static links to catalog routes and the maintained GET-route inventories, with explicit exceptions for the three mounted module routes. It reports unlisted Help destinations, unresolved catalog destinations, and entries lacking independent runtime validation. The test fails when global Help adds a module link without a catalog entry. This is **link-level coverage**, not an exhaustive audit of subfeatures, service methods or live behavior.

## Initial subfeature coverage

The first expansion adds 18 Help-documented subfeatures across Auction House, Live Client, Feature Trace, Wiki and Key Items. These entries are manually curated from operator-facing descriptions, not inferred from every API endpoint. The catalog remains incomplete for other large modules, and all newly added child records retain `unverified` runtime acceptance until evidence is recorded.

## Source-route expansion (October 18)

Twenty additional operator-facing pages were added from the maintained GET route inventory, bringing the curated inventory to 56 records at that historical checkpoint. These include missions, Assault, Nyzul, zones, client inspection, retail versions, dialog, capture search/query, migration converters, package review and validation runs. Static catalog route references were checked against the maintained route inventories; the Workbench regression workflow now runs `test_fixtures/test_feature_catalog.py` and triggers when `feature_catalog/**` changes. This still does not verify that the pages render in a configured Windows/DSP installation, or that every UI operation works.

## Active-page coverage gate

The coverage audit also compares catalog destinations with the maintained GET-route inventories' static `role: page` entries. It excludes root/Help/Roadmap/Catalog and parameterized paths; uncataloged `LEGACY` or `MERGE` disposition pages are reported separately rather than treated as active feature gaps. The regression fixture requires zero uncataloged active static pages. At the October 18 source-level checkpoint, 75 curated records cover the static active page inventory, with `/items` and `/backport/package` retained as uncataloged legacy/merge-target routes. This is not full dynamic-router, subfeature, browser-rendering, or Windows/DSP runtime acceptance.

## CI validation checkpoint

The initial Workbench Regression run failed in the newly added catalog smoke test because the test incorrectly assumed the query `binary` would match only one record. As the inventory grew, multiple valid records matched. The test now asserts inclusion of Binary Inspector rather than exclusive equality. That historical failure was fixed; later Workbench Regression runs passed. This does not constitute local Windows/browser acceptance.

## Quality and validation audit — October 19, 2026

The current curated inventory has **85 records**, comprising **38 subfeatures**; **67** are labelled implemented and **18** partial. Validation remains independent: **84 unverified**, **1 operator-reported**, **0 tested**. These numbers describe the catalog labels, not a claim about runtime capability. They supersede the historical record-count snapshots above.

The Coverage audit now displays module and subfeature totals, per-status counts, and missing purpose/usage/caveat fields. CI asserts status accounting against the actual JSON, rather than pinning record counts likely to change. UI-control inventory remains sampled and is not a claim of complete subfunction coverage. The next content-oriented slice is to attach real source/test references and review module-by-module whether key GUI actions have corresponding guided subfunction entries; runtime validation requires a separate observed acceptance record.

## Feature Testing and Wiki/Trace crosswalk — October 19, 2026

The next source-grounded expansion adds six curated capabilities: a parent Feature Testing & Validation entry, three operator-facing testing subfunctions (guided scenario builder, imported run inspector, read-only Supervisor investigation), a Feature Trace Wiki provenance drill-down, and exact Wiki page/section navigation. The catalog now has **91 entries**, subject to merge and CI. The existing `/feature-testing` mounted router is explicitly accounted for in source-route diagnostics rather than inventing a static endpoint in the maintained host route map.

All six new records remain **unverified** for local runtime acceptance. The descriptions distinguish design-only tests from supported execution and Wiki source evidence from verified DSP gameplay behavior. Subsequent work should inspect each major module's controls and functions against the curated catalog and attach independently reviewable source/test evidence, rather than automatically converting all endpoints to capabilities.
